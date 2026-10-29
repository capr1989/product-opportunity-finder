"""Bounded discovery strategies and evidence-first leads above existing collectors.

Sessions store snapshot identities, not copies of licensed product payloads. Collection
and financial validation remain separate; similarity never authorizes profit estimates.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import uuid

from rapidfuzz.fuzz import token_set_ratio

from pof.finance import Assumptions, calculate
from pof.live.catalog import source_status
from pof.live.discovery import run_research
from pof.live.query import ResearchQuery
from pof.matching import match, normalize, variants
from pof.models import now
from pof.research import pair_id
from pof.scoring import DEFAULT_WEIGHTS, score
from pof.storage import Store

TAXONOMY = {
    "Computer accessories": ("usb c hub", "wireless mouse", "laptop stand"),
    "Phone accessories": ("phone stand", "usb c charger", "phone case"),
    "Audio": ("wireless headphones", "bluetooth speaker", "wired earbuds"),
    "Home organization": ("desk organizer", "storage basket", "cable organizer"),
    "Kitchen tools": ("digital kitchen scale", "silicone spatula", "food storage containers"),
    "Fitness accessories": ("resistance bands", "yoga mat", "water bottle"),
}
SYNONYMS = {"type c": "usb c", "earphones": "earbuds", "cordless": "wireless",
            "notebook": "laptop", "adaptor": "adapter"}


@dataclass(frozen=True)
class DiscoverySettings:
    mode: str = "Quick Scan"
    business_model: str = "Explore All"
    market: str = "US"
    budget: float = 500
    minimum_profit: float = 5
    categories: tuple = ()
    query_limit: int = 3
    source_limit: int = 3
    products_per_source: int = 8
    max_delivery_days: int | None = None

    def __post_init__(self):
        if self.mode not in {"Quick Scan", "Deep Research"}:
            raise ValueError("Unknown discovery mode")
        if self.business_model not in {"Explore All", "Dropshipping", "Retail Reselling", "Wholesale"}:
            raise ValueError("Unknown business model")
        if self.market not in {"US", "PA", "US+PA"}:
            raise ValueError("Unsupported market")
        if not all(math.isfinite(v) and 0 <= v <= 1_000_000 for v in (self.budget, self.minimum_profit)):
            raise ValueError("Budget and desired profit must be finite and nonnegative")
        for value, maximum in ((self.query_limit, 12), (self.source_limit, 5), (self.products_per_source, 20)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("Research limits exceed the bounded workload")
        if any(c not in TAXONOMY for c in self.categories):
            raise ValueError("Unsupported category")
        if self.max_delivery_days is not None and not 1 <= self.max_delivery_days <= 365:
            raise ValueError("Delivery preference must be 1–365 days")


def canonical(text):
    text = normalize(text)
    for old, new in SYNONYMS.items():
        text = text.replace(old, new)
    return text


def followup_query(product):
    text = product.brand + " " + product.model if product.model else product.title
    return " ".join(canonical(text).split()[:12])[:180]


def plan_searches(settings, coverage):
    categories = list(settings.categories or TAXONOMY)
    categories.sort(key=lambda c: coverage.get(c, 0))
    plan = []
    for offset in range(3):
        for category in categories:
            terms = TAXONOMY[category]
            index = (coverage.get(category, 0) + offset) % len(terms)
            plan.append({"category": category, "query": terms[index], "strategy": "catalog discovery"})
    return plan[:settings.query_limit]


def available_sources(store, credentials, settings):
    names = []
    for name, config in store.configs("source").items():
        state = store.get_config("collection_state", name) or {}
        status = source_status(name, config, state, bool(credentials.get("BESTBUY_API_KEY")))
        if status["ready"]:
            names.append(name)
    # Supplier-first for direct fulfillment/wholesale; retailer-first otherwise.
    supplier_first = settings.business_model in {"Dropshipping", "Wholesale"}
    names.sort(key=lambda n: (store.get_config("source", n).get("role") !=
                             ("supplier" if supplier_first else "retailer"),
                             not bool((store.get_config("collection_state", n) or {}).get("verified_live")), n))
    return names[:settings.source_limit]


def build_leads(products, settings, assumptions=None, reviews=None):
    assumptions = assumptions or Assumptions()
    reviews = reviews or {}
    products = list({Store.identity(p): p for p in products if not p.demo}.values())[:300]
    rows, paired = [], set()
    for a in products:
        if settings.business_model in {"Dropshipping", "Wholesale"} and a.role != "supplier":
            continue
        for b in products:
            if a.source == b.source or b.role != "retailer" or a is b:
                continue
            similarity = token_set_ratio(canonical(a.title), canonical(b.title))
            m = match(a, b)
            if similarity < 55 and m.kind not in {"exact", "equivalent"}:
                continue
            if a.role == b.role and a.currency == b.currency and a.price is not None and b.price is not None and a.price > b.price:
                continue
            key = pair_id(a, b)
            decision = reviews.get(key, {}).get("decision", "automatic")
            accepted = m.kind in {"exact", "equivalent"} or decision == "approve"
            missing, reasons = [], []
            av, bv = variants(a), variants(b)
            conflict = (any(av[k] != bv[k] for k in av.keys() & bv.keys()) or
                        bool(a.gtin and b.gtin and a.gtin != b.gtin) or
                        bool(a.model and b.model and normalize(a.model) != normalize(b.model)))
            if decision == "reject" or conflict:
                reasons.append("Manual rejection" if decision == "reject" else m.reason)
            if not accepted:
                missing.append("Confirm product identity, variant, material and package quantity")
            if a.shipping is None:
                missing.append("Confirm inbound shipping per unit")
            if a.moq is None:
                missing.append("Confirm minimum order quantity")
            if a.currency != b.currency or a.currency != "USD":
                missing.append("Obtain comparable USD quotes; no currency conversion is assumed")
            if a.price is None or b.price is None:
                missing.append("Confirm both current unit prices")
            if a.condition == "unknown" or b.condition == "unknown":
                missing.append("Confirm product condition")
            if a.availability != "in_stock":
                missing.append("Confirm stock and fulfillment availability")
            if a.source_attributes.get("price_basis") == "advertised_minimum":
                missing.append("Confirm selected variant cost without minimum/coupon conditions")
            if a.state("price") == "stale" or b.state("price") == "stale":
                missing.append("Refresh stale prices")
            if settings.business_model == "Dropshipping":
                if a.role != "supplier" or a.moq != 1:
                    missing.append("Confirm single-unit direct fulfillment")
                if a.source_attributes.get("direct_fulfillment") is not True:
                    missing.append("Confirm supplier direct fulfillment to the customer")
            if settings.market != "US" and a.target_country not in {"PA", "Panama"}:
                missing.append("Confirm Panama delivery and import charges")
            if settings.max_delivery_days and (a.delivery_days is None or a.delivery_days > settings.max_delivery_days):
                missing.append("Confirm delivery within your preferred time")
            financial = calculate(a.price, b.price, a.shipping, a.moq, assumptions) if not missing and not reasons else {"known": False, "reason": "; ".join(missing + reasons)}
            feasible = None
            if financial["known"]:
                feasible = financial["inventory_commitment"] <= settings.budget
                if financial["contribution_profit"] < settings.minimum_profit:
                    reasons.append("Modeled contribution is below your desired profit")
                if not feasible:
                    reasons.append("Minimum inventory commitment exceeds your budget")
            gap = b.price - a.price if a.price is not None and b.price is not None and a.currency == b.currency else None
            state = "Rejected / Unattractive" if reasons else "Financially Evaluated" if financial["known"] else "Potential Lead"
            ranking, breakdown = score(a, financial, m.confidence, DEFAULT_WEIGHTS)
            rows.append({"id": key, "buy_id": Store.identity(a), "sell_id": Store.identity(b),
                         "state": state, "similarity": round(similarity, 1), "match_kind": m.kind,
                         "match_confidence": m.confidence, "match_reason": m.reason,
                         "observed_gap": gap, "currency": a.currency if gap is not None else "",
                         "financial": financial, "assumptions": asdict(assumptions), "missing": missing,
                         "reasons": reasons, "budget_feasible": feasible,
                         "score": ranking, "breakdown": breakdown,
                         "demand": "Verified keyword evidence; not sales" if a.monthly_searches is not None and a.state("monthly_searches") == "verified" else "Unknown",
                         "next_step": missing[0] if missing else "Review selling-price and cost assumptions before investing",
                         "promise": "Observed listing price difference; not profit" if gap is not None and gap > 0 else "Comparable listings worth checking"})
            paired.update((Store.identity(a), Store.identity(b)))
    for p in products:
        if Store.identity(p) not in paired:
            rows.append({"id": Store.identity(p), "buy_id": Store.identity(p), "sell_id": None,
                         "state": "Potential Lead", "observed_gap": None, "financial": {"known": False},
                         "missing": ["Find a comparable independent retail listing", "Verify variant, shipping and fulfillment"],
                         "reasons": [], "demand": "Unknown", "match_confidence": 0,
                         "next_step": "Search other sources for a comparable offer",
                         "promise": "Catalog discovery candidate; no price gap established"})
    return sorted(rows, key=lambda r: (r["state"] != "Rejected / Unattractive",
                  r["financial"].get("contribution_profit", -1_000_000),
                  r["observed_gap"] is not None and r["observed_gap"] > 0, r.get("score", 0), r["match_confidence"]), reverse=True)[:100]


def session_products(store, session):
    result = {}
    for run_id in session.get("run_ids", []):
        for p in store.products(run_id=run_id, demo=False):
            result[Store.identity(p)] = p
    seed_ids = set(session.get("seed_ids", []))
    for p in store.products(demo=False) if seed_ids else []:
        if Store.identity(p) in seed_ids:
            result.setdefault(Store.identity(p), p)
    # Existing explicit keyword associations remain evidence, never inferred sales.
    keywords = (store.get_config("keywords", "latest") or {}).get("rows", [])
    mappings = store.configs("keyword_map")
    for identity, p in result.items():
        mapping = mappings.get(identity, {})
        row = next((r for r in keywords if r.get("keyword") == mapping.get("keyword")), None)
        if row:
            p.monthly_searches = row.get("monthly_searches")
            p.demand_reference = row.copy()
            p.states["monthly_searches"] = row.get("status", "unavailable")
    return list(result.values())


def run_session(store, settings, credentials, *, session_id=None, seeds=(), progress=None,
                cancelled=None, collector=None, assumptions=None):
    collector = collector or run_research
    session = store.get_config("discovery_session", session_id) if session_id else None
    if session is None:
        coverage = store.get_config("discovery", "coverage") or {}
        plan = plan_searches(settings, coverage)
        if settings.mode == "Deep Research" and not seeds:
            plan = plan[:max(1, settings.query_limit // 2)]
        if settings.mode == "Deep Research" and seeds:
            plan = [{"category": "Follow-up", "query": followup_query(p),
                "strategy": "supplier-first" if p.role == "supplier" else "retailer-first"}
                for p in seeds if not p.demo and followup_query(p)][:settings.query_limit]
        names = available_sources(store, credentials, settings)
        session = {"id": uuid.uuid4().hex, "created": now(), "settings": asdict(settings),
                   "plan": plan, "sources": names, "completed": [], "run_ids": [],
                   "reports": [], "status": "running", "leads": [], "assumptions": asdict(assumptions or Assumptions())}
        session["seed_ids"] = [Store.identity(p) for p in seeds if not p.demo][:12]
        session["followups_planned"] = bool(seeds) or settings.mode != "Deep Research"
    else:
        settings = DiscoverySettings(**session["settings"])
    assumptions = Assumptions(**session["assumptions"])
    session["status"] = "running"
    store.put_config("discovery_session", session["id"], session)
    total = settings.query_limit * len(session["sources"])
    coverage = store.get_config("discovery", "coverage") or {}
    for index, task in enumerate(session["plan"]):
        for name in session["sources"]:
            task_id = f"{index}:{name}"
            if task_id in session["completed"]:
                continue
            if cancelled and cancelled():
                session["status"] = "paused"
                break
            if progress:
                role = store.get_config("source", name).get("role")
                progress(len(session["completed"]) / max(total, 1),
                         f"Searching {'suppliers' if role == 'supplier' else 'retailers'}: {name} · {task['query']}")
            query = ResearchQuery(keywords=task["query"], category_name=task["category"],
                                  target_market=settings.market, limit=settings.products_per_source,
                                  max_pages=1, available_only=False)
            cache_key = hashlib.sha256(json.dumps([name, asdict(query)], sort_keys=True).encode()).hexdigest()
            cached = store.get_config("discovery_cache", cache_key)
            # Cache references point at original immutable snapshots and retain original timestamps.
            fresh = cached and (datetime.now(timezone.utc) - datetime.fromisoformat(cached["created"])).total_seconds() < 900
            try:
                if name in session.get("restricted_sources", []):
                    session["reports"].append({"source": name, "status": "skipped", "error": "Earlier access barrier or rate limit; no further requests in this session."})
                    session["completed"].append(task_id)
                    store.put_config("discovery_session", session["id"], session)
                    continue
                if fresh and store.products(run_id=cached["run_id"], demo=False):
                    result = {"run_id": cached["run_id"], "reports": [{"source": name, "status": "recent snapshots reused", "error": ""}]}
                else:
                    result = collector(query, [name], store, credentials, refresh=False)
                    if store.products(run_id=result["run_id"], demo=False):
                        store.put_config("discovery_cache", cache_key, {"run_id": result["run_id"], "created": now()})
                session["run_ids"].append(result["run_id"])
                session["reports"].extend(result["reports"])
                if any(r.get("code") in {"access_barrier", "access_denied", "rate_limited", "credentials_rejected"} for r in result["reports"]):
                    session.setdefault("restricted_sources", []).append(name)
            except Exception:
                session["reports"].append({"source": name, "status": "failed", "error": "Collection could not finish safely; inspect Source Manager."})
            session["completed"].append(task_id)
            store.put_config("discovery_session", session["id"], session)
        if session["status"] == "paused":
            break
        if not session.get("coverage_recorded", {}).get(str(index)):
            coverage[task["category"]] = coverage.get(task["category"], 0) + 1
            session.setdefault("coverage_recorded", {})[str(index)] = True
        if index == len(session["plan"]) - 1 and not session["followups_planned"]:
            seen = {canonical(t["query"]) for t in session["plan"]}
            for p in session_products(store, session):
                query = followup_query(p)
                if not query or canonical(query) in seen or len(session["plan"]) >= settings.query_limit:
                    continue
                session["plan"].append({"category": "Follow-up", "query": query,
                                        "strategy": "supplier-first" if p.role == "supplier" else "retailer-first"})
                seen.add(canonical(query))
            session["followups_planned"] = True
            store.put_config("discovery_session", session["id"], session)
    if progress:
        progress(0.95, "Comparing products, investigating prices and ranking opportunities")
    session["leads"] = build_leads(session_products(store, session), settings, assumptions, store.reviews())
    if session["status"] != "paused":
        session["status"] = "complete" if total else "no_sources"
    session["updated"] = now()
    store.put_config("discovery", "coverage", coverage)
    store.put_config("discovery_session", session["id"], session)
    return session

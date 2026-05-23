"""
DailyMed REST API client.
Free, no registration required.
Docs: https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm
"""

import httpx

DAILYMED_BASE = "https://dailymed.nlm.nih.gov/dailymed/services/v2"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=DAILYMED_BASE, timeout=15.0)
    return _client


async def search_drug_names(name: str) -> list[dict]:
    client = _get_client()
    resp = await client.get("/drugnames.json", params={"drug_name": name})
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "name": item["drug_name"],
            "name_type": "brand" if item["name_type"] == "B" else "generic",
        }
        for item in data.get("data", [])
    ]


async def search_spls(
    drug_name: str | None = None,
    rxcui: int | None = None,
    ndc: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    client = _get_client()
    params: dict = {"page": page, "pagesize": page_size}
    if drug_name:
        params["drug_name"] = drug_name
    if rxcui:
        params["rxcui"] = rxcui
    if ndc:
        params["ndc"] = ndc

    resp = await client.get("/spls.json", params=params)
    resp.raise_for_status()
    data = resp.json()

    return {
        "labels": [
            {
                "setid": item["setid"],
                "title": item["title"],
                "published_date": item["published_date"],
                "version": item["spl_version"],
            }
            for item in data.get("data", [])
        ],
        "total": data.get("metadata", {}).get("total_elements", 0),
        "page": page,
        "total_pages": data.get("metadata", {}).get("total_pages", 0),
    }


async def get_spl_ndcs(setid: str) -> list[dict]:
    client = _get_client()
    resp = await client.get(f"/spls/{setid}/ndcs.json")
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


async def get_spl_packaging(setid: str) -> list[dict]:
    client = _get_client()
    resp = await client.get(f"/spls/{setid}/packaging.json")
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])

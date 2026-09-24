import io
import uuid
import pytest


async def _seed_sample_materials(client):
    csv_content = """organization,legacy_code,description,uom,item_name,part_number,manufacturer,category,material_type
ONGC,ONGC-VAL-001,"Ball Valve 2 inch 150# Flanged Body WCB",EA,"Ball Valve","BV-2-150","L&T Valves","Valves","Mechanical"
ONGC,ONGC-PMP-002,"Centrifugal Pump Impeller SS316 250mm",SET,"Pump Impeller","IMP-SS-316","KSB Pumps","Pumps","Rotating"
IOCL,IOCL-GSK-003,"Spiral Wound Gasket 4 inch 300# ASME",NOS,"Spiral Gasket",,"Flexitallic","Gaskets","Static"
BHEL,BHEL-TRB-004,"Steam Turbine Rotor Blade Stage 4 Inconel 718",EA,"Turbine Blade","TRB-BLD-04","BHEL Haridwar","Turbines","Turbomachinery"
GAIL,GAIL-PIP-005,"Seamless Carbon Steel Pipe 12 inch Sch 40",MTR,"CS Pipe","PIP-12-SCH40",,,"Piping"
CCL,CCL-BRG-006,"Spherical Roller Bearing 22220 E1 SKF",EA,"Roller Bearing","22220-E1","SKF Bearing","Bearings","Transmission"
"""
    files = {
        "file": ("sample_master.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
    }
    resp = await client.post("/api/v1/materials/ingest", files=files)
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_list_materials_default_pagination(client):
    await _seed_sample_materials(client)

    response = await client.get("/api/v1/materials")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data

    assert data["total"] == 6
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_pages"] == 1
    assert len(data["items"]) == 6


@pytest.mark.asyncio
async def test_pagination_pages_and_sizes(client):
    await _seed_sample_materials(client)

    # Page 1 with page_size=2
    resp_p1 = await client.get("/api/v1/materials?page=1&page_size=2")
    assert resp_p1.status_code == 200
    d1 = resp_p1.json()
    assert d1["total"] == 6
    assert d1["page"] == 1
    assert d1["page_size"] == 2
    assert d1["total_pages"] == 3
    assert len(d1["items"]) == 2

    # Page 2 with page_size=2
    resp_p2 = await client.get("/api/v1/materials?page=2&page_size=2")
    assert resp_p2.status_code == 200
    d2 = resp_p2.json()
    assert d2["page"] == 2
    assert len(d2["items"]) == 2

    # Verify no overlapping IDs between page 1 and page 2
    ids_p1 = {item["id"] for item in d1["items"]}
    ids_p2 = {item["id"] for item in d2["items"]}
    assert ids_p1.isdisjoint(ids_p2)


@pytest.mark.asyncio
async def test_search_by_legacy_code(client):
    await _seed_sample_materials(client)

    response = await client.get("/api/v1/materials?search=CCL-BRG")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["legacy_code"] == "CCL-BRG-006"
    assert data["items"][0]["organization"] == "CCL"


@pytest.mark.asyncio
async def test_search_by_description(client):
    await _seed_sample_materials(client)

    response = await client.get("/api/v1/materials?search=Inconel")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert "Inconel" in data["items"][0]["description"]
    assert data["items"][0]["organization"] == "BHEL"


@pytest.mark.asyncio
async def test_search_by_manufacturer_and_category(client):
    await _seed_sample_materials(client)

    # Search by manufacturer
    resp_mfg = await client.get("/api/v1/materials?search=SKF")
    assert resp_mfg.status_code == 200
    assert resp_mfg.json()["total"] == 1
    assert resp_mfg.json()["items"][0]["manufacturer"] == "SKF Bearing"

    # Search by category
    resp_cat = await client.get("/api/v1/materials?search=Pumps")
    assert resp_cat.status_code == 200
    assert resp_cat.json()["total"] == 1
    assert resp_cat.json()["items"][0]["category"] == "Pumps"


@pytest.mark.asyncio
async def test_organization_filtering(client):
    await _seed_sample_materials(client)

    response = await client.get("/api/v1/materials?organization=ONGC")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 2
    for item in data["items"]:
        assert item["organization"] == "ONGC"


@pytest.mark.asyncio
async def test_combined_search_and_organization_filter(client):
    await _seed_sample_materials(client)

    # Search "Impeller" in ONGC -> 1 result
    res1 = await client.get("/api/v1/materials?organization=ONGC&search=Impeller")
    assert res1.status_code == 200
    assert res1.json()["total"] == 1

    # Search "Impeller" in BHEL -> 0 results
    res2 = await client.get("/api/v1/materials?organization=BHEL&search=Impeller")
    assert res2.status_code == 200
    assert res2.json()["total"] == 0


@pytest.mark.asyncio
async def test_empty_search_result(client):
    await _seed_sample_materials(client)

    response = await client.get("/api/v1/materials?search=NonExistentTermXYZ999")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_get_organizations_endpoint(client):
    await _seed_sample_materials(client)

    response = await client.get("/api/v1/materials/organizations")
    assert response.status_code == 200
    orgs = response.json()

    assert isinstance(orgs, list)
    assert len(orgs) == 5
    assert set(orgs) == {"BHEL", "CCL", "GAIL", "IOCL", "ONGC"}
    # Verify alphabetical order
    assert orgs == sorted(orgs)


@pytest.mark.asyncio
async def test_get_quality_statistics_endpoint(client):
    await _seed_sample_materials(client)

    response = await client.get("/api/v1/materials/quality")
    assert response.status_code == 200
    data = response.json()

    assert data["total_materials"] == 6
    assert data["organizations"] == 5
    assert data["missing_uom"] == 0
    assert data["missing_manufacturer"] == 1  # GAIL pipe had no mfg
    assert data["missing_part_number"] == 1   # IOCL gasket had no part_no
    assert data["missing_category"] == 1      # GAIL pipe had no category


@pytest.mark.asyncio
async def test_get_material_detail_success(client):
    await _seed_sample_materials(client)

    list_res = await client.get("/api/v1/materials?limit=1")
    item = list_res.json()["items"][0]
    mat_id = item["id"]

    detail_res = await client.get(f"/api/v1/materials/{mat_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()

    assert detail["id"] == mat_id
    assert detail["legacy_code"] == item["legacy_code"]
    assert detail["description"] == item["description"]
    assert detail["organization"] == item["organization"]


@pytest.mark.asyncio
async def test_get_material_detail_not_found_404(client):
    non_existent_id = uuid.uuid4()
    response = await client.get(f"/api/v1/materials/{non_existent_id}")
    assert response.status_code == 404
    body = response.json()
    err_msg = body.get("error", {}).get("message") or body.get("detail", "")
    assert "not found" in err_msg.lower()


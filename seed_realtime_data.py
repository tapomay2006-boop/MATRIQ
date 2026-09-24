"""Real-time data synchronization script.
Seeds exactly:
- 50 materials with National IDs assigned (NMM-00000001 to NMM-00000050) across CPSEs
- 10 unassigned materials under CCL (status PENDING_REVIEW, national_id=None)
Syncs both materials_master (api-service) and material (ai-service) in PostgreSQL numm_ai.
"""

import asyncio
import hashlib
import uuid
from datetime import datetime
import pandas as pd
import asyncpg


def compute_canonical_hash(company: str, description: str, uom: str, part_no: str, make: str, spec: str) -> str:
    # 5 embedded fields
    text = (
        f"Item Description (Raw): {description}\n"
        f"UOM: {uom or 'NOS'}\n"
        f"Part Number / OEM Number: {part_no or 'N/A'}\n"
        f"Make / Brand: {make or 'N/A'}\n"
        f"Specifications / Dimensions: {spec or 'N/A'}"
    )
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()


async def main():
    print("Connecting to PostgreSQL numm_ai on 127.0.0.1:5432...")
    conn = await asyncpg.connect("postgresql://sih:sih@127.0.0.1:5432/numm_ai")

    # 1. Update schema for materials_master
    print("Ensuring materials_master columns national_id and status exist...")
    await conn.execute("""
        ALTER TABLE materials_master ADD COLUMN IF NOT EXISTS national_id VARCHAR(24);
        ALTER TABLE materials_master ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'AVAILABLE';
        CREATE INDEX IF NOT EXISTS ix_materials_master_national_id ON materials_master (national_id);
        CREATE INDEX IF NOT EXISTS ix_materials_master_status ON materials_master (status);
    """)

    # 2. Clear tables to remove outdated / mock / 404 rows
    print("Resetting materials_master, material, national_id_registry tables...")
    await conn.execute("TRUNCATE TABLE materials_master, material, national_id_registry RESTART IDENTITY CASCADE;")
    await conn.execute("UPDATE national_id_counter SET next_value = 51 WHERE id = 1;")

    # 3. Read raw CPSE items
    df = pd.read_csv("backend/pipeline-one/CPSE_SIH26099.csv")
    print(f"Loaded {len(df)} total catalogue rows from CPSE_SIH26099.csv.")

    # Select 50 diverse items for Assigned National IDs
    # Diversity across NTPC, BHEL, IOCL, GAIL, ONGC, HEC, and CCL
    assigned_records = []
    seen_hashes = set()
    seen_material_ids = set()

    for _, row in df.iterrows():
        desc = str(row.get("Item Description (Raw)", "")).strip()
        comp = str(row.get("Company", "")).strip()
        legacy = str(row.get("Item Code / Legacy Ref", "")).strip()
        uom = str(row.get("UOM", "")).strip() if pd.notna(row.get("UOM")) else "NOS"
        part_no = str(row.get("Part Number / OEM Number", "")).strip() if pd.notna(row.get("Part Number / OEM Number")) else "N/A"
        make = str(row.get("Make / Brand", "")).strip() if pd.notna(row.get("Make / Brand")) else "N/A"
        spec = str(row.get("Specifications / Dimensions", "")).strip() if pd.notna(row.get("Specifications / Dimensions")) else "N/A"
        qty = float(row.get("Quantity", 1)) if pd.notna(row.get("Quantity")) and row.get("Quantity") != "" else 10.0

        if not desc or desc.lower() == "nan":
            continue

        c_hash = compute_canonical_hash(comp, desc, uom, part_no, make, spec)
        if c_hash in seen_hashes:
            continue
        seen_hashes.add(c_hash)

        # Map CPSE code
        cpse_code = "CCL" if "coal india" in comp.lower() or "ccl" in comp.lower() or "bccl" in comp.lower() else comp
        if "ntpc" in comp.lower(): cpse_code = "NTPC"
        elif "bhel" in comp.lower(): cpse_code = "BHEL"
        elif "iocl" in comp.lower(): cpse_code = "IOCL"
        elif "gail" in comp.lower(): cpse_code = "GAIL"
        elif "ongc" in comp.lower(): cpse_code = "ONGC"
        elif "hec" in comp.lower(): cpse_code = "HEC"

        raw_legacy = legacy if legacy and legacy.lower() != "nan" else f"{cpse_code}-{1000 + len(assigned_records)}"
        mat_id = f"{cpse_code}-{raw_legacy}"
        if mat_id in seen_material_ids:
            raw_legacy = f"{raw_legacy}-{len(assigned_records)+1}"
            mat_id = f"{cpse_code}-{raw_legacy}"
        seen_material_ids.add(mat_id)

        assigned_records.append({
            "company": comp,
            "cpse_code": cpse_code,
            "legacy_code": raw_legacy,
            "description": desc,
            "uom": uom,
            "part_number": part_no,
            "make": make,
            "spec": spec,
            "quantity": qty,
            "canonical_hash": c_hash,
        })
        if len(assigned_records) == 50:
            break

    print(f"Curated {len(assigned_records)} assigned items.")

    # 4. Insert 50 Assigned Records
    now = datetime.utcnow()
    for idx, item in enumerate(assigned_records, start=1):
        national_seq = idx
        national_id = f"NMM-{national_seq:08d}"
        mat_uuid = uuid.uuid4()
        material_id = f"{item['cpse_code']}-{item['legacy_code']}"

        # Category rule (simple keyword mapping)
        desc_u = item['description'].upper()
        cat = "UNCLASSIFIED"
        if "BEARING" in desc_u or "BRG" in desc_u: cat = "BEARING"
        elif "VALVE" in desc_u or "VLV" in desc_u: cat = "VALVE"
        elif "BELT" in desc_u: cat = "BELT"
        elif "PUMP" in desc_u: cat = "PUMP"
        elif "FILTER" in desc_u: cat = "FILTER"
        elif "GASKET" in desc_u: cat = "GASKET"
        elif "MOTOR" in desc_u: cat = "MOTOR"
        elif "SWITCH" in desc_u: cat = "ELECTRICAL"
        elif "SHOE" in desc_u or "HELMET" in desc_u or "SAFETY" in desc_u: cat = "SAFETY"
        elif "TOOTH" in desc_u or "BUCKET" in desc_u or "DRAGLINE" in desc_u: cat = "MINING_HEMM"

        # 4a. Insert into materials_master (api-service)
        await conn.execute("""
            INSERT INTO materials_master (
                id, organization, legacy_code, description, uom, item_name,
                part_number, manufacturer, equipment_compatibility, material_type,
                category, specification, national_id, status, source_file, source_row, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
        """,
            mat_uuid,
            item["cpse_code"],
            item["legacy_code"],
            item["description"],
            item["uom"],
            item["description"][:50],
            item["part_number"],
            item["make"],
            "Standard CPSE Equipment",
            "Consumable Spares",
            cat,
            item["spec"],
            national_id,
            "ASSIGNED",
            "CPSE_SIH26099.csv",
            idx,
            now,
            now,
        )

        # 4b. Insert into material (ai-service)
        await conn.execute("""
            INSERT INTO material (
                id, material_id, source_row, cpse_code, cpse_name, legacy_code,
                description_raw, uom_raw, quantity, part_number_raw, manufacturer_raw,
                specifications_raw, created_at, updated_at, status, national_id, national_seq,
                category, unit_price, total_inventory_value, currency, canonical_hash,
                embedding_version, indexed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
        """,
            str(mat_uuid),
            material_id,
            idx,
            item["cpse_code"],
            item["company"],
            item["legacy_code"],
            item["description"],
            item["uom"],
            item["quantity"],
            item["part_number"],
            item["make"],
            item["spec"],
            now,
            now,
            "ASSIGNED",
            national_id,
            national_seq,
            cat,
            4500.0,
            item["quantity"] * 4500.0,
            "INR",
            item["canonical_hash"],
            "deterministic-v1",
            now,
        )

        # 4c. Insert into national_id_registry
        await conn.execute("""
            INSERT INTO national_id_registry (
                national_id, national_seq, canonical_title, category, codification_authority, allocated_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
            national_id,
            national_seq,
            item["description"][:60],
            cat,
            "NUMM National Harmonization Authority",
            now,
        )

    print("Successfully inserted 50 assigned materials with NMM-00000001 to NMM-00000050.")

    # 5. Insert 10 Unassigned Materials under CCL
    # Distinct mining, mechanical, and processing plant items
    ccl_unassigned = [
        {
            "legacy_code": "CCL-HEMM-UN-001",
            "description": "NEMISYS HEAVY DUTY TOOTH POINT FOR ESCO 24/96 DRAGLINE BUCKET",
            "uom": "SET",
            "part_number": "ESCO-N1-94821",
            "make": "ESCO",
            "spec": "Alloy Steel Cast, Wear Cap Compatible, Rig: Dragline 24/96",
            "qty": 8.0,
            "cat": "MINING_HEMM",
        },
        {
            "legacy_code": "CCL-HEMM-UN-002",
            "description": "HYDRAULIC RETURN OIL FILTER CARTRIDGE 10 MICRON FOR BEML 100T DUMPER",
            "uom": "NOS",
            "part_number": "HF-6510-BEML",
            "make": "FLEETGUARD",
            "spec": "Glass fibre media, 10 micron rating, Burst press 35 bar",
            "qty": 24.0,
            "cat": "FILTER",
        },
        {
            "legacy_code": "CCL-PLANT-UN-003",
            "description": "HIGH PRESSURE SLURRY VALVE 150MM FLANGED ANSI 300# RUBBER LINED",
            "uom": "NOS",
            "part_number": "SLV-150-RBL",
            "make": "AUDCO",
            "spec": "Body: WCB, Lining: Natural soft rubber 6mm, ANSI 300",
            "qty": 6.0,
            "cat": "VALVE",
        },
        {
            "legacy_code": "CCL-ELEC-UN-004",
            "description": "FLAMEPROOF SQUIRREL CAGE INDUCTION MOTOR 55KW 415V 1480RPM EX-D GROUP I",
            "uom": "SET",
            "part_number": "MOT-55KW-FLP1",
            "make": "BBL",
            "spec": "Flameproof Ex-d Group I for underground coal mines, Class F, IP65",
            "qty": 2.0,
            "cat": "MOTOR",
        },
        {
            "legacy_code": "CCL-CONV-UN-005",
            "description": "STEEL CORD CONVEYOR BELT ST-1250 WIDTH 1200MM GRADE M24 COVER 8+4MM",
            "uom": "MTR",
            "part_number": "ST-1250-1200",
            "make": "FENNER",
            "spec": "Tensile ST 1250 N/mm, Top cover 8mm, Bottom cover 4mm, Fire resistant",
            "qty": 450.0,
            "cat": "BELT",
        },
        {
            "legacy_code": "CCL-PUMP-UN-006",
            "description": "HIGH CHROME HEAVY SLURRY PUMP IMPELLER 5-VANE FOR WARMAN 8/6 PUMP",
            "uom": "NOS",
            "part_number": "WAR-E4147-A05",
            "make": "WEIR WARMAN",
            "spec": "Material: Ultrachrome A05 high chrome alloy, 5-vane closed impeller",
            "qty": 4.0,
            "cat": "PUMP",
        },
        {
            "legacy_code": "CCL-BRG-UN-007",
            "description": "SPHERICAL ROLLER BEARING 23230 CC/W33 C3 CLEARANCE WITH OIL GROOVE",
            "uom": "NOS",
            "part_number": "23230-CC/W33-C3",
            "make": "SKF",
            "spec": "Bore 150mm, OD 270mm, Width 96mm, Steel cage, C3 clearance",
            "qty": 12.0,
            "cat": "BEARING",
        },
        {
            "legacy_code": "CCL-PUMP-UN-008",
            "description": "MECHANICAL SEAL CARTRIDGE TYPE 75MM SIC/SIC/VITON FOR ASH WATER PUMP",
            "uom": "SET",
            "part_number": "MSEAL-75-SSV",
            "make": "FLOWSERVE",
            "spec": "Faces: Silicon Carbide vs Silicon Carbide, Elastomer: FKM Viton",
            "qty": 5.0,
            "cat": "PUMP",
        },
        {
            "legacy_code": "CCL-SAFE-UN-009",
            "description": "DGMS APPROVED MINER SAFETY BOOTS WITH STEEL TOE AND MIDSOLE SIZE 8",
            "uom": "PAIR",
            "part_number": "SAFE-BOOT-M08",
            "make": "BATA INDUSTRIAL",
            "spec": "Full grain water resistant leather, Steel toe 200J, DGMS Approval No 421",
            "qty": 120.0,
            "cat": "SAFETY",
        },
        {
            "legacy_code": "CCL-PIPE-UN-010",
            "description": "SPIRAL WELDED MS SLURRY PIPE 300MM NB SCHEDULE 40 IS:3589 WITH FLANGES",
            "uom": "MTR",
            "part_number": "PIP-MS-300NB",
            "make": "TATA STEEL",
            "spec": "Nominal Bore 300mm, Wall thickness 9.52mm, Length 6M with welded flanges",
            "qty": 180.0,
            "cat": "UNCLASSIFIED",
        },
    ]

    for idx, item in enumerate(ccl_unassigned, start=51):
        mat_uuid = uuid.uuid4()
        material_id = f"CCL-{item['legacy_code']}"
        c_hash = compute_canonical_hash("Coal India (Central Coalfields Limited)", item['description'], item['uom'], item['part_number'], item['make'], item['spec'])

        # 5a. Insert into materials_master (api-service) with national_id = NULL, status = PENDING_REVIEW
        await conn.execute("""
            INSERT INTO materials_master (
                id, organization, legacy_code, description, uom, item_name,
                part_number, manufacturer, equipment_compatibility, material_type,
                category, specification, national_id, status, source_file, source_row, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NULL, 'PENDING_REVIEW', $13, $14, $15, $16)
        """,
            mat_uuid,
            "CCL",
            item["legacy_code"],
            item["description"],
            item["uom"],
            item["description"][:50],
            item["part_number"],
            item["make"],
            "CCL HEMM & Coal Washery Operations",
            "Mining Inventory Spares",
            item["cat"],
            item["spec"],
            "ccl_inbound_catalog.csv",
            idx,
            now,
            now,
        )

        # 5b. Insert into material (ai-service) with national_id = NULL, status = PENDING_REVIEW
        await conn.execute("""
            INSERT INTO material (
                id, material_id, source_row, cpse_code, cpse_name, legacy_code,
                description_raw, uom_raw, quantity, part_number_raw, manufacturer_raw,
                specifications_raw, created_at, updated_at, status, national_id, national_seq,
                category, unit_price, total_inventory_value, currency, canonical_hash,
                embedding_version, indexed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, 'PENDING_REVIEW', NULL, NULL, $15, $16, $17, 'INR', $18, 'deterministic-v1', $19)
        """,
            str(mat_uuid),
            material_id,
            idx,
            "CCL",
            "Coal India (Central Coalfields Limited)",
            item["legacy_code"],
            item["description"],
            item["uom"],
            item["qty"],
            item["part_number"],
            item["make"],
            item["spec"],
            now,
            now,
            item["cat"],
            12500.0,
            item["qty"] * 12500.0,
            c_hash,
            now,
        )

    print("Successfully inserted 10 unassigned materials under CCL.")

    # 6. Verification counts
    master_cnt = await conn.fetchval("SELECT count(*) FROM materials_master;")
    master_assigned = await conn.fetchval("SELECT count(*) FROM materials_master WHERE national_id IS NOT NULL;")
    master_ccl_unassigned = await conn.fetchval("SELECT count(*) FROM materials_master WHERE organization = 'CCL' AND national_id IS NULL;")

    ai_cnt = await conn.fetchval("SELECT count(*) FROM material;")
    ai_assigned = await conn.fetchval("SELECT count(*) FROM material WHERE national_id IS NOT NULL;")
    ai_ccl_unassigned = await conn.fetchval("SELECT count(*) FROM material WHERE cpse_code = 'CCL' AND national_id IS NULL;")

    registry_cnt = await conn.fetchval("SELECT count(*) FROM national_id_registry;")

    print("\n--- SYNCHRONIZATION SUMMARY ---")
    print(f"materials_master (api-service): Total = {master_cnt} | Assigned = {master_assigned} | CCL Unassigned = {master_ccl_unassigned}")
    print(f"material (ai-service):         Total = {ai_cnt} | Assigned = {ai_assigned} | CCL Unassigned = {ai_ccl_unassigned}")
    print(f"national_id_registry:          Total = {registry_cnt}")
    print("Database is completely synchronized and cleanly seeded!")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://sih:sih@127.0.0.1:5432/numm_ai')
    orgs = await conn.fetch('SELECT organization, count(*) as cnt FROM materials_master GROUP BY organization')
    print('materials_master orgs:')
    for o in orgs:
        print(f"  {o['organization']}: {o['cnt']}")
    
    m_orgs = await conn.fetch('SELECT cpse_code, count(*) as cnt, count(national_id) as assigned FROM material GROUP BY cpse_code')
    print('\nmaterial table orgs:')
    for o in m_orgs:
        print(f"  {o['cpse_code']}: total {o['cnt']}, national_id: {o['assigned']}")

    mat_sample = await conn.fetch('SELECT material_id, cpse_code, national_id, description_raw FROM material LIMIT 5')
    print('\nmaterial sample:')
    for m in mat_sample:
        print(f"  {m['material_id']} | {m['cpse_code']} | {m['national_id']} | {m['description_raw'][:40]}")

    master_sample = await conn.fetch('SELECT id, organization, legacy_code, description FROM materials_master LIMIT 5')
    print('\nmaterials_master sample:')
    for m in master_sample:
        print(f"  {m['id']} | {m['organization']} | {m['legacy_code']} | {m['description'][:40]}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())

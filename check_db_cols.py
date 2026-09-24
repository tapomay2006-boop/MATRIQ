import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://sih:sih@127.0.0.1:5432/numm_ai')
    for table in ['materials_master', 'material', 'national_id_registry', 'duplicate_match']:
        cols = await conn.fetch(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """)
        print(f"\n--- TABLE: {table} ---")
        for c in cols:
            print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())

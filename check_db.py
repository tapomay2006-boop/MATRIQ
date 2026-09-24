import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://sih:sih@127.0.0.1:5432/numm_ai')
    rows = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    for r in rows:
        t = r['table_name']
        try:
            cnt = await conn.fetchval(f'SELECT count(*) FROM "{t}"')
            print(f'{t}: {cnt} rows')
        except Exception as e:
            print(f'{t}: error {e}')
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())

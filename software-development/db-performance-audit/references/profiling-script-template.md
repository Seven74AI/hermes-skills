# Profiling Script Template

Standalone Node.js script for profiling Prisma queries against a seeded dev DB. Place in `scripts/profile-queries.ts` and run with `npx tsx scripts/profile-queries.ts`.

```ts
import { PrismaClient } from '#prisma/client.js'
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3'

const adapter = new PrismaBetterSqlite3({ url: 'file:data.db' })
const prisma = new PrismaClient({ adapter })

async function profile(name: string, fn: () => Promise<unknown>, iterations = 10) {
  // Warmup
  await fn()
  // Measure
  const times: number[] = []
  for (let i = 0; i < iterations; i++) {
    const start = performance.now()
    await fn()
    times.push(performance.now() - start)
  }
  times.sort((a, b) => a - b)
  const median = times[Math.floor(times.length / 2)]
  console.log(`${name}: ${median.toFixed(1)}ms (median of ${iterations})`)
  return median
}

async function main() {
  // Example: profile a route loader
  const { loader } = await import('../app/routes/_app._index/home.server.ts')
  
  const before = await profile('home loader (before)', async () => {
    await loader({ request: new Request('http://localhost'), params: {}, context: {} })
  })

  // ... apply fix, re-profile ...

  const after = await profile('home loader (after)', async () => {
    await loader({ request: new Request('http://localhost'), params: {}, context: {} })
  })

  console.log(`\nImprovement: ${((1 - after / before) * 100).toFixed(0)}%`)
  await prisma.$disconnect()
}

main()
```

## Raw SQL micro-benchmark template

When comparing individual operations (upsert vs findUnique, COUNT vs groupBy):

```ts
const N = 5000

// BEFORE
const t1 = performance.now()
for (let i = 0; i < N; i++) {
  await prisma.$executeRawUnsafe('INSERT INTO t(id,val) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET val=val', `k${i%10}`, 'x')
}
const beforeMs = performance.now() - t1

// AFTER
const t2 = performance.now()
for (let i = 0; i < N; i++) {
  await prisma.$executeRawUnsafe('SELECT 1 FROM t WHERE id=?', `k${i%10}`)
}
const afterMs = performance.now() - t2

console.log(`${(beforeMs/N).toFixed(4)}ms → ${(afterMs/N).toFixed(4)}ms = ${((1 - afterMs/beforeMs)*100).toFixed(0)}%`)
```

/**
 * Large seed template — creates realistic data volumes for perf profiling.
 *
 * Customize: TOTAL_TRACKS, ARTIST_COUNT, PLAYLIST_SIZES, user details below.
 * Then run:
 *   rm -f prisma/perf.db
 *   DATABASE_URL="file:./prisma/perf.db?connection_limit=1" npx prisma migrate deploy
 *   DATABASE_URL="file:./prisma/perf.db?connection_limit=1" npx tsx --conditions=react-server prisma/seed-large.ts
 *
 * ⚠️ createMany skipDuplicates is unsupported on SQLite — always use a fresh DB.
 */

import 'dotenv/config'
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3'
import { PrismaClient } from '#prisma/client.js'

const prisma = new PrismaClient({ adapter: new PrismaBetterSqlite3({ url: process.env.DATABASE_URL! }) })

const TOTAL_TRACKS = 10_000
const ARTIST_COUNT = 50
const PLAYLIST_SIZES = [500, 750, 1000, 1500, 2000, 2500, 3000, 4000, 4500, 5000]
const BATCH_SIZE = 500

async function seed() {
  console.log('Seeding...')
  const t0 = performance.now()

  const youtube = await prisma.service.upsert({
    where: { name: 'youtube' }, update: {},
    create: { name: 'youtube', displayName: 'YouTube', baseUrl: 'https://youtube.com', isActive: true },
  })

  const user = await prisma.user.upsert({
    where: { username: 'perftest' }, update: {},
    create: { email: 'perf@test.dev', username: 'perftest', name: 'Perf Tester' },
  })

  const artistIds: string[] = []
  for (let i = 0; i < ARTIST_COUNT; i++) {
    const name = `Artist ${String(i).padStart(3, '0')}`
    const a = await prisma.artist.upsert({
      where: { normalizedName: name.toLowerCase() }, update: {},
      create: { name, normalizedName: name.toLowerCase() },
    })
    artistIds.push(a.id)
  }

  for (let b = 0; b < TOTAL_TRACKS; b += BATCH_SIZE) {
    const end = Math.min(b + BATCH_SIZE, TOTAL_TRACKS)
    await prisma.$transaction([
      prisma.track.createMany({
        data: Array.from({ length: end - b }, (_, i) => ({
          id: `perf-track-${String(b + i).padStart(5, '0')}`,
          title: `Track ${String(b + i).padStart(5, '0')}`,
          artistId: artistIds[(b + i) % ARTIST_COUNT],
          serviceId: youtube.id,
          externalId: `ext-perf-${b + i}`,
          duration: 180 + ((b + i) % 300),
        })),
      }),
      prisma.userTrack.createMany({
        data: Array.from({ length: end - b }, (_, i) => ({
          userId: user.id,
          trackId: `perf-track-${String(b + i).padStart(5, '0')}`,
        })),
      }),
    ])
  }

  for (let p = 0; p < PLAYLIST_SIZES.length; p++) {
    const pl = await prisma.userPlaylist.create({ data: { title: `Playlist ${p + 1}`, ownerId: user.id } })
    for (let t = 0; t < PLAYLIST_SIZES[p]; t += BATCH_SIZE) {
      const end = Math.min(t + BATCH_SIZE, PLAYLIST_SIZES[p])
      await prisma.userPlaylistTrack.createMany({
        data: Array.from({ length: end - t }, (_, i) => ({
          playlistId: pl.id,
          trackId: `perf-track-${String((t + i) % TOTAL_TRACKS).padStart(5, '0')}`,
          position: t + i,
        })),
      })
    }
  }

  for (let p = 0; p < PLAYLIST_SIZES.length; p++) {
    const pl = await prisma.servicePlaylist.create({
      data: { title: `YT Playlist ${p + 1}`, serviceId: youtube.id, externalId: `yt-pl-${p}`, itemCount: PLAYLIST_SIZES[p], ownerId: user.id, isActive: true },
    })
    for (let t = 0; t < PLAYLIST_SIZES[p]; t += BATCH_SIZE) {
      const end = Math.min(t + BATCH_SIZE, PLAYLIST_SIZES[p])
      await prisma.servicePlaylistTrack.createMany({
        data: Array.from({ length: end - t }, (_, i) => ({
          playlistId: pl.id,
          trackId: `perf-track-${String((t + i) % TOTAL_TRACKS).padStart(5, '0')}`,
          position: t + i,
          isDeleted: false,
        })),
      })
    }
  }

  console.log(`Done in ${((performance.now() - t0) / 1000).toFixed(1)}s`)
  await prisma.$disconnect()
}

seed().catch((e) => { console.error(e); process.exit(1) })

# @types/node v26 Migration

## Breaking change: `rmdirSync` options removed

In `@types/node` v26, `fs.rmdirSync()` no longer accepts an options object as the second argument. Use `fs.rmSync()` instead.

```ts
// ❌ @types/node v22
fs.rmdirSync(path.dirname(deepPath), { recursive: true })

// ✅ @types/node v26+
fs.rmSync(path.dirname(deepPath), { recursive: true })
```

`rmSync` has identical behavior and has been available since Node 14.14.0.

## Finding all occurrences

```bash
rg "rmdirSync" --include='*.ts' --include='*.tsx'
```

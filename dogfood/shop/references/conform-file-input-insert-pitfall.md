# Conform Field Array Insert + File Input Loss

## Symptom

When testing forms that use Conform's `form.insert.getButtonProps()` to add file input fields, the file selection on EXISTING file inputs is lost after clicking the "Add" button. Only the LAST file input retains its selected file.

## Root Cause

React cannot preserve file input values (`<input type="file">`) across re-renders — this is a browser security restriction. When Conform's `form.insert` adds a new field to the array and triggers a component re-render, the React reconciliation process recreates the file input elements. The browser discards the previously selected file because JavaScript cannot programmatically set `File` objects on file inputs.

## Real Case

`note-images.test.ts:35` — "Users can create note with multiple images". The original test order:
1. `setInputFiles` on input[0] (cute-koala.png)
2. Fill alt text[0]
3. Click "Add image" button → Conform inserts new field → re-render → **file input[0] loses its file**
4. `setInputFiles` on input[1] (koala-coder.png)
5. Fill alt text[1]
6. Submit → only one image saved (koala-coder)

The page snapshot confirmed only one image was displayed on the note detail page.

## Fix

**Add all fields BEFORE setting any files.** The field insertion triggers the re-render while no files are selected yet, so nothing is lost:

```ts
// ✅ CORRECT ORDER — add fields first, then set files
await page.getByRole('textbox', { name: 'title' }).fill(newNote.title)
await page.getByRole('textbox', { name: 'content' }).fill(newNote.content)
await page.getByRole('button', { name: 'add image' }).click()  // ← BEFORE any setInputFiles

await page.getByLabel('image').nth(0).setInputFiles('...cute-koala.png')
await page.getByLabel('alt text').nth(0).fill(altText1)

await page.getByLabel('image').nth(1).setInputFiles('...koala-coder.png')
await page.getByLabel('alt text').nth(1).fill(altText2)

await page.getByRole('button', { name: 'submit' }).click()
```

## Detection Pattern

When a multi-image upload test creates N images but only the Nth image appears on the result page, and the test uses Conform's `getFieldset` / `getFieldList` / `form.insert`, suspect this pattern. The page YAML snapshot will show fewer `<img>` elements than expected.

## Scope

This affects ANY test that:
1. Uses `setInputFiles` on a file input
2. Then triggers a React re-render (via Conform `form.insert`, `form.remove`, or any state change that remounts file inputs)
3. Then submits the form

The workaround is always: structure the test so file inputs are set AFTER the last state-changing interaction.

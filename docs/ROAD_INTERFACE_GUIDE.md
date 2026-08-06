# Road interface guide overlay

The front-page **Guide** button opens the interactive walkthrough for the Road
data preparation model. Its content is intentionally maintained as data rather
than embedded in the page markup.

## Updating the guide

Edit `front-end/road-model-guide.js` and add, remove, or reorder an object in
`ROAD_MODEL_GUIDE_STEPS`:

```js
{
    target: '#element-id',
    title: 'Short step title',
    copy: 'Plain-language explanation of what the researcher can do here.'
}
```

`target` is a CSS selector for the element to highlight. For resilient steps,
provide alternatives separated by commas; the first element that exists is
used. Add `image` and `imageAlt` for a screenshot stored under
`front-end/assets/guide/`, or `placeholder` when the screenshot will be added
later. Use `gallery` with an ordered array of `{ image, alt }` objects when a
single step needs several screenshots; the user can move through that gallery
without advancing the tour. Use `table` with `caption`, `headers`, and `rows`
for compact reference tables. Keep the explanation focused on both the
immediate action and its role in the road-to-LEAP Outlook workflow.

The current LEAP galleries use `front-end/assets/guide/leap-workbook/` and
`front-end/assets/guide/lifecycle-profiles/`. To update their screenshots,
replace the image files there and retain their ordered filenames, or update the
corresponding `gallery` array in `road-model-guide.js` when adding or removing
steps.

The interaction code and styling are deliberately generic. A guide update
normally requires no edits outside the steps array unless a new interface area
needs a stable ID.

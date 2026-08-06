# Road interface guide overlay

The front-page **Tour** button opens the interactive walkthrough for the Road
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
without advancing the tour. Add `caption` to a gallery image when it needs an
instruction below the screenshot. Add `images: [{ image, alt }, ...]` to one
gallery item when related screenshots should appear side by side. Use `table` with `caption`, `headers`, and `rows`
for compact reference tables. Keep the explanation focused on both the
immediate action and its role in the road-to-LEAP Outlook workflow.

The current guide screenshots are local authoring assets under
`front-end/assets/guide/`; they are intentionally ignored by Git because the
Hugging Face deployment rejects binary PNG files. To update screenshots,
replace the images while retaining their manifest paths, then run
`scripts/build_road_model_guide_images.py`. Commit the resulting
`front-end/road-model-guide-images.js` file. Update the manifest and the
corresponding `gallery` array in `road-model-guide.js` when adding or removing
steps. Also increment the cache suffix on that script's tag in
`front-end/index.html` so browsers load the updated image bundle.

The interaction code and styling are deliberately generic. A guide update
normally requires no edits outside the steps array unless a new interface area
needs a stable ID.

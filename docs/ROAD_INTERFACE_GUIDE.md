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
used. Keep the explanation focused on both the immediate action and its role in
the road-to-LEAP Outlook workflow.

The interaction code and styling are deliberately generic. A guide update
normally requires no edits outside the steps array unless a new interface area
needs a stable ID.

![alt text](shishuoSketch.png)
# 世說Sketch

## Source processing

The Kanripo source-processing pipeline is documented in
[docs/source-processing.md](docs/source-processing.md). It normalizes the
immutable TXT sources into provenance-preserving Markdown and segments
Shishuo Xinyu into chapter/editorial records without simplifying the
traditional Chinese text or extracting relationships.

Run the focused tests with:

```sh
python3 -m unittest discover -s tests -v
```

# Sample Data

Add your CATIA Draft Analysis screenshots here:
- `sample1.png`: Example passing draft analysis
- `sample2.png`: Example with draft angle issues

These images should be 2D screenshots from CATIA with color-coded regions:
- **Green regions**: Pass (acceptable draft angle)
- **Red regions**: Fail (draft angle issues)

## How to Use Sample Data

Place your exported CATIA Draft Analysis images in this directory, then run:

```bash
python app.py data/your_image.png --output ./reports
```

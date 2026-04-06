# Draft Angle Checker - CAD Validation Tool

An automated computer vision tool for validating draft angles in CAD parts using CATIA draft analysis screenshots.

## Overview

This tool analyzes CATIA Draft Analysis screenshots (which use color coding: **green for pass**, **red for fail**) to:
- Detect and quantify failing draft angle regions
- Calculate pass/fail percentages
- Generate automated validation reports
- Support batch processing of CAD designs

## Project Structure

```
draft-angle-checker/
├── data/                    # Sample images and test data
│   ├── sample1.png
│   └── sample2.png
├── src/
│   ├── image_processor.py   # Image loading and preprocessing
│   ├── analyzer.py          # Draft analysis logic
│   └── report.py            # Report generation
├── app.py                   # Main application entry point
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Installation

1. Clone or download the project:
```bash
cd draft-angle-checker
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Analyze a single image:
```bash
python app.py path/to/image.png
```

### Advanced Options

```bash
# Set custom pass threshold (default: 80%)
python app.py path/to/image.png --threshold 75

# Save reports to output directory
python app.py path/to/image.png --output ./reports

# Generate both text and JSON reports
python app.py path/to/image.png --output ./reports --format both

# Generate only JSON report
python app.py path/to/image.png --output ./reports --format json
```

## Features

### Image Processing (`src/image_processor.py`)
- Loads and preprocesses CAD draft analysis images
- Converts BGR to HSV color space for robust color detection
- Extracts red (fail) and green (pass) regions
- Applies morphological operations for noise reduction
- Histogram analysis support

### Analysis Engine (`src/analyzer.py`)
- Detects color-coded regions (pass/fail)
- Calculates pass/fail percentages based on pixel counts
- Configurable pass threshold (default: 80%)
- Provides detailed pixel statistics
- Binary mask extraction for visualization

### Report Generation (`src/report.py`)
- Text-formatted reports with detailed statistics
- JSON export for programmatic access
- Timestamp tracking
- Configurable output paths
- Console output display

## How It Works

1. **Image Input**: Takes a 2D screenshot of CATIA Draft Analysis
2. **Color Detection**: Identifies green (pass) and red (fail) regions using HSV color space
3. **Pixel Analysis**: Counts passing and failing pixels
4. **Calculation**: Computes pass/fail percentages
5. **Report**: Generates detailed validation report

## Example Report

```
============================================================
DRAFT ANGLE ANALYSIS REPORT
============================================================
Timestamp: 2026-04-06 14:30:45
Image: data/sample1.png

------------------------------------------------------------
RESULTS
------------------------------------------------------------
Status: PASS
Pass Percentage: 92.50%
Fail Percentage: 7.50%
Pass Threshold: 80%

------------------------------------------------------------
PIXEL STATISTICS
------------------------------------------------------------
Pass Pixels (Green): 185000
Fail Pixels (Red): 15000
Total Pixels: 200000

------------------------------------------------------------
✓ DRAFT ANGLE ACCEPTABLE FOR MANUFACTURING
============================================================
```

## Configuration

### Color Detection Ranges

You can customize color detection parameters in `ImageProcessor`:

```python
# Red threshold ranges (HSV)
processor.extract_red_mask(lower_hue=0, upper_hue=10, ...)

# Green threshold ranges (HSV)
processor.extract_green_mask(lower_hue=40, upper_hue=80, ...)
```

### Pass Threshold

Default is 80% pass acceptance. Adjust when running analysis:

```python
analyzer.get_status(pass_threshold=75)  # Require 75% pass rate
```

## API Reference

### DraftAnalyzer

```python
from src.analyzer import DraftAnalyzer

analyzer = DraftAnalyzer('image.png')
analyzer.analyze()

# Get results
status = analyzer.get_status(pass_threshold=80)  # 'PASS' or 'FAIL'
summary = analyzer.get_analysis_summary()
```

### ImageProcessor

```python
from src.image_processor import ImageProcessor

processor = ImageProcessor('image.png')
red_mask = processor.extract_red_mask()
green_mask = processor.extract_green_mask()
```

### Report

```python
from src.report import Report

report = Report(analysis_summary, image_path)
report.print_report()
report.save_text_report('output.txt')
report.save_json_report('output.json')
```

## Exit Codes

- `0`: Analysis completed successfully, draft angles acceptable (PASS)
- `1`: Analysis completed, draft angles need review (FAIL) or error occurred

## Future Enhancements

- CNN-based classification for more complex scenarios
- Real-time CATIA integration
- Batch processing capabilities
- Web UI for result visualization
- Multi-part assembly analysis
- Historical trend analysis

## Requirements

- Python 3.7+
- OpenCV 4.5.0+
- NumPy 1.20.0+

## License

This project is created for CAD validation and quality assurance purposes.

## Support

For issues or questions, refer to the source code documentation in each module.

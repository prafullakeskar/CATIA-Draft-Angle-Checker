import argparse
import sys
from pathlib import Path
from flask import Flask, request, render_template_string, jsonify
from src.analyzer import DraftAnalyzer
from src.report import Report

UPLOAD_PAGE = '''
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Draft Angle Checker</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 2rem; background: #f4f7fb; color: #1c1f26; }
      .container { max-width: 700px; margin: auto; background: white; padding: 2rem; border-radius: 10px; box-shadow: 0 6px 18px rgba(0,0,0,0.08); }
      h1 { margin-top: 0; }
      .result { margin: 1rem 0; padding: 1rem; border-radius: 8px; }
      .pass { background: #e8f7ea; border: 1px solid #9fe0af; color: #266a32; }
      .fail { background: #fde8e8; border: 1px solid #f2a3a3; color: #8b1f1f; }
      .error { background: #fff2e8; border: 1px solid #f0c27b; color: #7a4f0c; }
      label { display: block; margin: 1rem 0 0.5rem; }
      input[type="file"], input[type="number"] { width: 100%; padding: 0.75rem; border-radius: 6px; border: 1px solid #cbd5e1; }
      button { margin-top: 1rem; padding: 0.9rem 1.4rem; border: none; border-radius: 6px; background: #2563eb; color: white; font-size: 1rem; cursor: pointer; }
      button:hover { background: #1d4ed8; }
      pre { background: #f4f7fb; padding: 1rem; border-radius: 8px; overflow-x: auto; }
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Draft Angle Checker</h1>
      <p>Upload your CATIA draft analysis image and get a quick&nbsp;OK/NOT&nbsp;OK result.</p>

      {% if error %}
        <div class="result error">{{ error }}</div>
      {% endif %}

      {% if status_text %}
        <div class="result {{ 'pass' if summary.status == 'PASS' else 'fail' }}">
          <strong>Result:</strong> {{ status_text }}
          <br>
          Status: {{ summary.status }}
          <br>
          Pass: {{ summary.pass_percentage }}% | Fail: {{ summary.fail_percentage }}%
        </div>
      {% endif %}

      <form method="post" enctype="multipart/form-data">
        <label for="image">Select image</label>
        <input type="file" name="image" id="image" accept="image/*" required>

        <label for="threshold">Pass threshold (%)</label>
        <input type="number" name="threshold" id="threshold" value="80" min="0" max="100" step="1">

        <button type="submit">Analyze Image</button>
      </form>

      {% if summary %}
        <h2>Details</h2>
        <pre>{{ summary | tojson(indent=2) }}</pre>
      {% endif %}
    </div>
  </body>
</html>
'''


def analyze_image_bytes(image_bytes, pass_threshold=80):
    analyzer = DraftAnalyzer(image_bytes)
    analyzer.analyze()
    return analyzer.get_analysis_summary(pass_threshold=pass_threshold)


def build_flask_app():
    app = Flask(__name__)

    @app.route('/', methods=['GET', 'POST'])
    def index():
        error = None
        summary = None
        status_text = None

        if request.method == 'POST':
            uploaded_file = request.files.get('image')
            if not uploaded_file or uploaded_file.filename == '':
                error = 'Please upload an image file.'
            else:
                try:
                    threshold = float(request.form.get('threshold', '80'))
                except ValueError:
                    threshold = 80

                try:
                    image_bytes = uploaded_file.read()
                    summary = analyze_image_bytes(image_bytes, pass_threshold=threshold)
                    status_text = 'OK' if summary['status'] == 'PASS' else 'NOT OK'
                except Exception as exc:
                    error = str(exc)

        return render_template_string(UPLOAD_PAGE, error=error, summary=summary, status_text=status_text)

    @app.route('/api/analyze', methods=['POST'])
    def api_analyze():
        if 'image' not in request.files:
            return jsonify({'error': 'No image uploaded.'}), 400

        uploaded_file = request.files['image']
        if uploaded_file.filename == '':
            return jsonify({'error': 'Empty filename.'}), 400

        try:
            threshold = float(request.form.get('threshold', '80'))
        except ValueError:
            threshold = 80

        try:
            summary = analyze_image_bytes(uploaded_file.read(), pass_threshold=threshold)
            return jsonify({
                'ok': summary['status'] == 'PASS',
                'summary': summary
            })
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500

    return app


def cli_main():
    """Main command-line entry point for the draft angle checker."""
    parser = argparse.ArgumentParser(
        description='Draft Angle Checker - Validate CAD draft angles from CATIA screenshots'
    )
    parser.add_argument(
        'image',
        help='Path to the CATIA draft analysis image'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=80,
        help='Pass threshold percentage (default: 80)'
    )
    parser.add_argument(
        '--output',
        help='Output report path (optional)'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json', 'both'],
        default='text',
        help='Report format (default: text)'
    )

    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f'Error: Image file not found: {image_path}')
        return 1

    try:
        print(f'Analyzing: {image_path}')
        analyzer = DraftAnalyzer(str(image_path))
        analyzer.analyze()
        summary = analyzer.get_analysis_summary(pass_threshold=args.threshold)

        report = Report(summary, image_path)
        report.print_report()

        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)

            if args.format in ['text', 'both']:
                text_path = output_dir / 'report.txt'
                report.save_text_report(text_path)
                print(f'\nText report saved to: {text_path}')

            if args.format in ['json', 'both']:
                json_path = output_dir / 'report.json'
                report.save_json_report(json_path)
                print(f'JSON report saved to: {json_path}')

        return 0 if summary['status'] == 'PASS' else 1
    except Exception as e:
        print(f'Error: {str(e)}')
        return 1


def run_web_server():
    app = build_flask_app()
    app.run(host='0.0.0.0', port=5000)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run_web_server()
    else:
        exit(cli_main())

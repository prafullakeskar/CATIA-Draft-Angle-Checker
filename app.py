import argparse
from pathlib import Path
from src.analyzer import DraftAnalyzer
from src.report import Report


def main():
    """Main entry point for the draft angle checker."""
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
    
    # Validate image path
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image file not found: {image_path}")
        return 1
    
    try:
        # Analyze the image
        print(f"Analyzing: {image_path}")
        analyzer = DraftAnalyzer(str(image_path))
        analyzer.analyze()
        
        # Get results
        summary = analyzer.get_analysis_summary(pass_threshold=args.threshold)
        
        # Generate report
        report = Report(summary, image_path)
        
        # Print to console
        report.print_report()
        
        # Save report if requested
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            if args.format in ['text', 'both']:
                text_path = output_dir / 'report.txt'
                report.save_text_report(text_path)
                print(f"\nText report saved to: {text_path}")
            
            if args.format in ['json', 'both']:
                json_path = output_dir / 'report.json'
                report.save_json_report(json_path)
                print(f"JSON report saved to: {json_path}")
        
        # Return appropriate exit code
        return 0 if summary['status'] == 'PASS' else 1
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


if __name__ == '__main__':
    exit(main())

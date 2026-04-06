import json
from datetime import datetime
from pathlib import Path


class Report:
    """Generates reports from draft angle analysis."""
    
    def __init__(self, analysis_summary, image_path=None):
        """
        Initialize the report.
        
        Args:
            analysis_summary: Dictionary with analysis results
            image_path: Path to the source image (optional)
        """
        self.analysis_summary = analysis_summary
        self.image_path = image_path
        self.timestamp = datetime.now()
    
    def generate_text_report(self):
        """Generate a text-based report."""
        report = []
        report.append("=" * 60)
        report.append("DRAFT ANGLE ANALYSIS REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if self.image_path:
            report.append(f"Image: {self.image_path}")
        
        report.append("\n" + "-" * 60)
        report.append("RESULTS")
        report.append("-" * 60)
        report.append(f"Status: {self.analysis_summary['status']}")
        report.append(f"Pass Percentage: {self.analysis_summary['pass_percentage']:.2f}%")
        report.append(f"Fail Percentage: {self.analysis_summary['fail_percentage']:.2f}%")
        report.append(f"Pass Threshold: {self.analysis_summary['pass_threshold']}%")
        
        report.append("\n" + "-" * 60)
        report.append("PIXEL STATISTICS")
        report.append("-" * 60)
        report.append(f"Pass Pixels (Green): {self.analysis_summary['pass_pixels']}")
        report.append(f"Fail Pixels (Red): {self.analysis_summary['fail_pixels']}")
        report.append(f"Total Pixels: {self.analysis_summary['total_pixels']}")
        
        report.append("\n" + "-" * 60)
        
        if self.analysis_summary['status'] == 'PASS':
            report.append("✓ DRAFT ANGLE ACCEPTABLE FOR MANUFACTURING")
        else:
            report.append("✗ DRAFT ANGLE ISSUES DETECTED")
            report.append(f"  Failing regions: {self.analysis_summary['fail_percentage']:.2f}%")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def generate_json_report(self):
        """Generate a JSON-formatted report."""
        report_data = {
            'timestamp': self.timestamp.isoformat(),
            'image_path': str(self.image_path) if self.image_path else None,
            'analysis_results': self.analysis_summary
        }
        return json.dumps(report_data, indent=2)
    
    def save_text_report(self, output_path):
        """
        Save the text report to a file.
        
        Args:
            output_path: Path to save the report
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(self.generate_text_report())
        
        return str(output_path)
    
    def save_json_report(self, output_path):
        """
        Save the JSON report to a file.
        
        Args:
            output_path: Path to save the report
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(self.generate_json_report())
        
        return str(output_path)
    
    def print_report(self):
        """Print the text report to console."""
        print(self.generate_text_report())

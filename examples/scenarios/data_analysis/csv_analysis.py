"""CSV data analysis with visualization.

This example demonstrates:
- Reading and processing CSV files
- Statistical analysis with pandas
- Data visualization with matplotlib
- Multiple output formats (text, images, CSV)
- Comprehensive error handling

Usage:
    python examples/scenarios/data_analysis/csv_analysis.py
    
    # Or with your own CSV file:
    python examples/scenarios/data_analysis/csv_analysis.py path/to/data.csv
"""

import sys
from pathlib import Path


def analyze_csv_agent():
    """Analyze CSV data and create visualizations."""
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import seaborn as sns
    from pathlib import Path
    import json
    from datetime import datetime
    
    print("Starting CSV analysis agent...")
    
    # Look for CSV file in workspace
    workspace = Path("/workspace")
    csv_files = list(workspace.glob("*.csv"))
    
    if not csv_files:
        print("No CSV file found in workspace. Creating sample dataset...")
        # Create sample sales data
        dates = pd.date_range('2024-01-01', periods=365, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'sales': [1000 + i * 5 + (i % 30) * 50 + (i % 7) * 20 for i in range(365)],
            'customers': [50 + i // 7 + (i % 10) * 3 for i in range(365)],
            'revenue': [5000 + i * 25 + (i % 15) * 100 for i in range(365)],
            'region': ['North', 'South', 'East', 'West'][i % 4] for i in range(365)
        })
        csv_path = workspace / "sample_data.csv"
        df.to_csv(csv_path, index=False)
        print(f"✓ Created sample dataset with {len(df)} rows")
    else:
        csv_path = csv_files[0]
        print(f"Found CSV file: {csv_path.name}")
    
    try:
        # Load data
        print(f"Loading data from {csv_path.name}...")
        df = pd.read_csv(csv_path)
        print(f"✓ Loaded {len(df)} rows and {len(df.columns)} columns")
        print(f"  Columns: {', '.join(df.columns)}")
        
        # Basic info
        print("\nData types:")
        for col, dtype in df.dtypes.items():
            print(f"  {col}: {dtype}")
        
        # Statistical analysis
        print("\nPerforming statistical analysis...")
        
        # Get numeric columns
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
        
        if not numeric_cols:
            raise ValueError("No numeric columns found for analysis")
        
        summary_stats = df[numeric_cols].describe()
        correlations = df[numeric_cols].corr()
        
        print(f"✓ Analyzed {len(numeric_cols)} numeric columns")
        
        # Create visualizations
        print("\nCreating visualizations...")
        
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (16, 12)
        
        # Create subplots
        n_plots = min(len(numeric_cols), 4)
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        axes = axes.flatten()
        
        # Plot 1: Time series or line plot
        if 'date' in df.columns:
            try:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date')[numeric_cols[:3]].plot(ax=axes[0])
                axes[0].set_title("Time Series Analysis", fontsize=14, fontweight='bold')
                axes[0].set_xlabel("Date")
                axes[0].set_ylabel("Values")
                axes[0].legend()
            except:
                df[numeric_cols[:3]].plot(ax=axes[0])
                axes[0].set_title("Line Plot", fontsize=14, fontweight='bold')
        else:
            df[numeric_cols[:3]].plot(ax=axes[0])
            axes[0].set_title("Line Plot", fontsize=14, fontweight='bold')
        
        # Plot 2: Distribution histograms
        df[numeric_cols].hist(ax=axes[1], bins=30, alpha=0.7)
        axes[1].set_title("Distribution Histograms", fontsize=14, fontweight='bold')
        
        # Plot 3: Correlation heatmap
        if len(numeric_cols) > 1:
            sns.heatmap(correlations, annot=True, fmt='.2f', cmap='coolwarm', 
                       center=0, ax=axes[2], square=True)
            axes[2].set_title("Correlation Matrix", fontsize=14, fontweight='bold')
        
        # Plot 4: Box plots
        df[numeric_cols[:4]].boxplot(ax=axes[3])
        axes[3].set_title("Box Plots (Outlier Detection)", fontsize=14, fontweight='bold')
        axes[3].set_xlabel("Variables")
        axes[3].set_ylabel("Values")
        plt.setp(axes[3].xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        # Prepare outputs
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save visualization
        viz_path = output_dir / "analysis_visualization.png"
        plt.savefig(viz_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved visualization: {viz_path.name}")
        plt.close()
        
        # Create additional plots
        if len(numeric_cols) >= 2:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(df[numeric_cols[0]], df[numeric_cols[1]], alpha=0.5)
            ax.set_xlabel(numeric_cols[0])
            ax.set_ylabel(numeric_cols[1])
            ax.set_title(f"{numeric_cols[0]} vs {numeric_cols[1]}", fontsize=14, fontweight='bold')
            scatter_path = output_dir / "scatter_plot.png"
            plt.savefig(scatter_path, dpi=300, bbox_inches='tight')
            print(f"✓ Saved scatter plot: {scatter_path.name}")
            plt.close()
        
        # Save statistical summary
        summary_path = output_dir / "statistical_summary.txt"
        with open(summary_path, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write("CSV DATA ANALYSIS REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"File: {csv_path.name}\n")
            f.write(f"Rows: {len(df)}\n")
            f.write(f"Columns: {len(df.columns)}\n")
            f.write(f"Analyzed: {datetime.now().isoformat()}\n\n")
            f.write("=" * 60 + "\n")
            f.write("DESCRIPTIVE STATISTICS\n")
            f.write("=" * 60 + "\n\n")
            f.write(summary_stats.to_string())
            f.write("\n\n")
            f.write("=" * 60 + "\n")
            f.write("CORRELATION MATRIX\n")
            f.write("=" * 60 + "\n\n")
            f.write(correlations.to_string())
            f.write("\n\n")
            f.write("=" * 60 + "\n")
            f.write("MISSING VALUES\n")
            f.write("=" * 60 + "\n\n")
            missing = df.isnull().sum()
            f.write(missing.to_string())
            f.write("\n")
        
        print(f"✓ Saved statistical summary: {summary_path.name}")
        
        # Save correlations as CSV
        corr_path = output_dir / "correlations.csv"
        correlations.to_csv(corr_path)
        print(f"✓ Saved correlations: {corr_path.name}")
        
        # Create insights
        insights = []
        
        # Find highest correlation
        if len(numeric_cols) > 1:
            corr_values = correlations.values
            for i in range(len(corr_values)):
                for j in range(i+1, len(corr_values)):
                    if abs(corr_values[i][j]) > 0.7:
                        insights.append(
                            f"Strong correlation ({corr_values[i][j]:.2f}) between "
                            f"{numeric_cols[i]} and {numeric_cols[j]}"
                        )
        
        # Find columns with missing values
        missing_cols = df.isnull().sum()
        for col, count in missing_cols.items():
            if count > 0:
                pct = (count / len(df)) * 100
                insights.append(f"{col} has {count} missing values ({pct:.1f}%)")
        
        # Save insights
        insights_path = output_dir / "insights.txt"
        with open(insights_path, 'w') as f:
            f.write("KEY INSIGHTS\n")
            f.write("=" * 60 + "\n\n")
            if insights:
                for i, insight in enumerate(insights, 1):
                    f.write(f"{i}. {insight}\n")
            else:
                f.write("No significant insights detected.\n")
        
        print(f"✓ Saved insights: {insights_path.name}")
        
        # Save metadata
        metadata = {
            "filename": csv_path.name,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": df.columns.tolist(),
            "numeric_columns": numeric_cols,
            "missing_values": df.isnull().sum().to_dict(),
            "analyzed_at": datetime.now().isoformat()
        }
        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✓ Saved metadata: {metadata_path.name}")
        
        print("\n✓ Analysis completed successfully")
        print(f"\nGenerated {len(list(output_dir.glob('*')))} output files")
        
        return f"Analyzed {len(df)} rows with {len(numeric_cols)} numeric columns"
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        print(f"✗ {error_msg}")
        
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "error.txt").write_text(error_msg)
        
        raise


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy
    
    # Check if custom CSV file provided
    custom_csv = None
    if len(sys.argv) > 1:
        custom_csv = Path(sys.argv[1])
        if not custom_csv.exists():
            print(f"Error: File not found: {custom_csv}", file=sys.stderr)
            sys.exit(1)
    
    # Setup directories
    workspace = Path("./workspace/data_analysis")
    workspace.mkdir(parents=True, exist_ok=True)
    
    output = Path("./output/data_analysis")
    output.mkdir(parents=True, exist_ok=True)
    
    # Copy custom CSV if provided
    if custom_csv:
        import shutil
        shutil.copy(custom_csv, workspace / custom_csv.name)
        print(f"Copied {custom_csv.name} to workspace")
    
    print("=" * 60)
    print("CSV Data Analysis Agent")
    print("=" * 60)
    print()
    
    # Configure policy
    policy = Policy(
        cpu_cores=2.0,
        memory_mb=2048,
        timeout_seconds=180,
        pip_packages=[
            "pandas",
            "matplotlib",
            "seaborn",
            "numpy"
        ]
    )
    
    print("Launching agent in isolated container...")
    print()
    
    # Run agent
    result = run_agent(
        agent=analyze_csv_agent,
        working_dir=workspace,
        host_output_path=output,
        policy=policy
    )
    
    print()
    print("=" * 60)
    
    if result.exit_code == 0:
        print("✓ Analysis completed successfully")
        print()
        
        if result.artifacts:
            print("Generated artifacts:")
            for name, path in result.artifacts.items():
                file_path = Path(path)
                if file_path.exists():
                    size = file_path.stat().st_size
                    print(f"  • {name} ({size:,} bytes)")
            
            # Show insights
            insights_path = result.artifacts.get("insights.txt")
            if insights_path and Path(insights_path).exists():
                print()
                print("Key Insights:")
                print("-" * 60)
                print(Path(insights_path).read_text())
                print("-" * 60)
    else:
        print(f"✗ Analysis failed with exit code {result.exit_code}")
        if result.error:
            print(f"Error: {result.error}")
    
    print("=" * 60)
    
    sys.exit(result.exit_code)

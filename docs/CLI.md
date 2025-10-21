# CLI Documentation

This document provides comprehensive documentation for Tkonverter's command-line interface.

## Overview

Tkonverter CLI provides full feature parity with the GUI application through a command-line interface. It's designed for automation, scripting, and integration into larger workflows.

## Installation

The CLI uses the same virtual environment as the GUI application. No additional installation is required.

```bash
# Make sure the main application is set up first
./launcher.sh install

# Then use the CLI
./tkonverter-cli.sh --help
```

## Commands

### `convert` - Convert JSON to Text

Converts Telegram chat export to readable text format.

```bash
# Basic conversion
./tkonverter-cli.sh convert -i result.json -o output.txt

# With custom settings
./tkonverter-cli.sh convert -i result.json -o output.txt --profile personal --no-time

# Using configuration file
./tkonverter-cli.sh convert -i result.json -o output.txt --config config.json

# HTML output
./tkonverter-cli.sh convert -i result.json -o output.html --html-mode
```

**Options:**
- `-i, --input`: Input JSON file path (required)
- `-o, --output`: Output text file path (required)
- `--profile`: Chat profile type (group/personal/posts/channel)
- `--config, -c`: Path to configuration file
- `--html-mode`: Generate HTML output instead of plain text
- `--overwrite`: Overwrite output file if it exists

**Configuration Options:**
- `--show-time` / `--no-time`: Show/hide timestamps
- `--show-reactions` / `--no-reactions`: Show/hide reactions
- `--show-markdown` / `--no-markdown`: Show/hide markdown formatting
- `--show-links` / `--no-links`: Show/hide links
- `--my-name`: Your name in personal chats
- `--partner-name`: Partner name in personal chats
- `--streak-break-time`: Streak break time in HH:MM format

### `analyze` - Analyze Chat Statistics

Analyzes chat statistics, token counts, and provides detailed analytics.

```bash
# Character analysis only
./tkonverter-cli.sh analyze -i result.json --chars-only

# Token analysis (requires transformers library)
./tkonverter-cli.sh analyze -i result.json --tokenizer google/gemma-2b

# Save results to file
./tkonverter-cli.sh analyze -i result.json --chars-only --output results.json

# Date filtering
./tkonverter-cli.sh analyze -i result.json --from-date 2025-01-01 --to-date 2025-12-31
```

**Options:**
- `-i, --input`: Input JSON file path (required)
- `--tokenizer`: Tokenizer model name (e.g., google/gemma-2b)
- `--chars-only`: Analyze characters only (skip tokenization)
- `--output`: Save analysis results to file
- `--from-date`: Start date (YYYY-MM-DD)
- `--to-date`: End date (YYYY-MM-DD)
- `--exclude-dates`: Dates to exclude (YYYY-MM-DD)

### `info` - Show File Information

Shows information about chat export file without full conversion.

```bash
# Basic file information
./tkonverter-cli.sh info -i result.json

# Detailed information
./tkonverter-cli.sh info -i result.json --detailed

# Validation only
./tkonverter-cli.sh info -i result.json --validate-only
```

**Options:**
- `-i, --input`: Input JSON file path (required)
- `--detailed`: Show detailed parsing statistics
- `--validate-only`: Only validate file without loading full chat

## Configuration Files

CLI supports JSON configuration files for complex setups:

```json
{
  "profile": "group",
  "show_time": true,
  "show_reactions": true,
  "show_reaction_authors": false,
  "my_name": "Me",
  "partner_name": "Partner",
  "show_optimization": false,
  "streak_break_time": "20:00",
  "show_markdown": true,
  "show_links": true,
  "show_tech_info": true,
  "show_service_notifications": true
}
```

Configuration files can be combined with CLI arguments. CLI arguments take precedence over configuration file settings.

## Examples

### Batch Processing

```bash
#!/bin/bash
# Process multiple chat exports

for file in exports/*.json; do
    filename=$(basename "$file" .json)
    ./tkonverter-cli.sh convert -i "$file" -o "output/${filename}.txt" --profile group
    ./tkonverter-cli.sh analyze -i "$file" --chars-only --output "analysis/${filename}.json"
done
```

### Automated Analysis

```bash
#!/bin/bash
# Analyze chat and generate report

chat_file="result.json"
analysis_file="analysis.json"

# Run analysis
./tkonverter-cli.sh analyze -i "$chat_file" --chars-only --output "$analysis_file"

# Extract key metrics
total_chars=$(jq '.analysis.total_characters' "$analysis_file")
total_messages=$(jq '.chat_info.total_messages' "$analysis_file")

echo "Chat Analysis Report"
echo "==================="
echo "Total Messages: $total_messages"
echo "Total Characters: $total_chars"
echo "Average Message Length: $((total_chars / total_messages))"
```

### Date Filtering

```bash
# Analyze only recent messages
./tkonverter-cli.sh analyze -i result.json \
    --from-date 2025-01-01 \
    --chars-only \
    --output recent_analysis.json

# Exclude specific dates
./tkonverter-cli.sh analyze -i result.json \
    --exclude-dates 2025-01-01 2025-01-02 \
    --chars-only
```

## Error Handling

The CLI provides detailed error messages and appropriate exit codes:

- `0`: Success
- `1`: General error (file not found, validation failed, etc.)
- `2`: Argument parsing error
- `130`: Interrupted by user (Ctrl+C)

## Debug Mode

Enable debug logging for troubleshooting:

```bash
./tkonverter-cli.sh --debug convert -i result.json -o output.txt
```

## Integration

The CLI can be easily integrated into larger workflows:

- **CI/CD pipelines**: Automated processing of chat exports
- **Data analysis**: Batch processing for research
- **Backup systems**: Automated conversion of chat archives
- **Monitoring**: Regular analysis of chat statistics

## Performance

The CLI is optimized for performance:

- **Memory efficient**: Processes large files without loading everything into memory
- **Fast startup**: No GUI initialization overhead
- **Parallel processing**: Can be run in parallel for batch operations
- **Caching**: Reuses existing virtual environment and dependencies

## Troubleshooting

### Common Issues

1. **File not found**: Ensure the input file exists and path is correct
2. **Permission denied**: Check file permissions for input/output files
3. **Invalid JSON**: Verify the input file is a valid Telegram export
4. **Tokenizer errors**: Install transformers library for token analysis

### Getting Help

```bash
# General help
./tkonverter-cli.sh --help

# Command-specific help
./tkonverter-cli.sh convert --help
./tkonverter-cli.sh analyze --help
./tkonverter-cli.sh info --help
```

from scripts import auto_label_openclaw
from pathlib import Path
import subprocess


def main():
    # ensure enriched file exists and prefer it
    enriched = Path('data/labels/annotation_bulk_enriched_openclaw.csv')
    infile = str(enriched if enriched.exists() else Path('data/labels/annotation_bulk.csv'))
    out = 'data/labels/annotation_bulk_openclaw.csv'
    auto_label_openclaw.main(infile=infile, out=out)


if __name__ == '__main__':
    main()

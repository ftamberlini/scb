# Runtime data

The application reads ANCINE files from `data/ancine` and optional IMDb files
from `data/imdb`. The large Parquet files are intentionally not stored in Git.

For local development, place the source files in those directories or set
`ANCINE_DATA_DIR` and `DATA_DIR` to external directories. Docker builds copy
the local `data` directory, so production builds must provision the Parquet
files in the build context before `docker build` runs.

The empty directories are committed so a clean checkout and the Docker build
have a predictable layout. Tests create their own small temporary datasets.

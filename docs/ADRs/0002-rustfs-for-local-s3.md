# ADR 0002: RustFS instead of MinIO for local object storage

**Status:** Accepted (Phase 0, 2026-11-13). Amends ADR 0001.

## Context
`docker compose up` failed: `minio/minio` and `minio/mc` no longer exist on Docker Hub, and the
`quay.io/minio/*` mirror returns 401. We need a local S3-compatible store for resume files.

## Decision
Use **RustFS** (`rustfs/rustfs`) as the local S3 server, on the same ports MinIO used
(9000 = S3 API, 9001 = web console) and with the same dev credentials, so `backend/.env` is
unchanged. The `screeniq-resumes` bucket is created by a one-shot `amazon/aws-cli` container
(`s3-init`) using the plain S3 API instead of MinIO's `mc` tool.

Production is unchanged: Cloudflare R2 or AWS S3.

## Why
- The backend only talks the S3 API (`S3_ENDPOINT` + keys), so the server behind it is swappable.
- RustFS is open source, actively maintained, and the closest drop-in for MinIO (same ports,
  similar env-var config, a bucket-browsing console).
- SeaweedFS also works but has no comparable console and needs more setup.

## Consequences
- RustFS here only supports **path-style** addressing (`http://host:9000/bucket/key`). In Phase 3
  the S3 client must set path-style addressing (boto3: `Config(s3={"addressing_style": "path"})`).
  R2 supports path-style too, so one setting works everywhere.
- Signed URLs generated inside Docker use the `rustfs` hostname; the browser needs
  `localhost:9000`. Phase 3 must handle this (a separate public endpoint setting).

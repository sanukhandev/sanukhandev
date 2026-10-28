---
title: "25 Million Records Later: Why Your RAG Pipeline Still Isn't Production-Ready"
published: false
description: "A practical architecture review of AWS's Ray-based RAG ingestion pipeline—and the reliability, security, and retrieval gates needed to operate RAG in production."
tags: rag, architecture, aws, ai
---

> **25 million records. Distributed GPUs. Two vector databases. And still, the most difficult part of production RAG is not embedding generation.**

A RAG prototype is easy to demo:

```text
PDF → chunks → embeddings → vector DB → LLM → answer
```

But production is where the questions change.

What if a policy PDF is revised after it has been indexed? What if an ingestion worker retries the same batch? What if a user from Tenant A retrieves a chunk owned by Tenant B? What if the vector index returns a confident but obsolete paragraph?

Those failures do not disappear by adding GPUs.

I recently revisited AWS's article, [Build a RAG data ingestion pipeline for large-scale ML workloads](https://aws.amazon.com/blogs/big-data/build-a-rag-data-ingestion-pipeline-for-large-scale-ml-workloads/), published March 13, 2024. It is an interesting, substantial experiment. This article examines what it gets right, what it does *not* establish, and how I would extend the design for production.

## What AWS actually built

AWS demonstrates a batch ETL pipeline:

```text
OSCAR JSONL corpus
        ↓
AWS Glue → Parquet on S3
        ↓
Ray cluster on GPU-backed EC2
        ↓
Chunking + all-mpnet-base-v2 embeddings
        ↓
       ┌────────────┴─────────────┐
       ↓                          ↓
OpenSearch (HNSW)        RDS PostgreSQL + pgvector (IVF)
       └────────────┬─────────────┘
                    ↓
           Simulated retrieval queries
```

The original OSCAR corpus is described as approximately 609 million records; AWS uses a **25-million-record subset** for the experiment. It reports a Ray setup of **five g4dn.12xlarge instances**, each with four NVIDIA T4 GPUs, and the **all-mpnet-base-v2** model producing **768-dimensional embeddings**. These are details from the AWS experiment, **not results from my own benchmark**.

The key idea is sound: if embedding generation is your bottleneck, parallelizing that workload is more useful than simply tuning the vector database.

## Three things this architecture gets right

### 1. It separates bulk data preparation from embedding generation

Converting large JSONL datasets to Parquet before distributed processing is a sensible design choice. Columnar formats can reduce I/O overhead and make batch reads more efficient.

### 2. It treats embeddings as a distributed compute problem

Embedding generation can be GPU-bound. Ray makes it possible to distribute work rather than feeding a large corpus through one long-running Python process. It also exposes execution telemetry.

### 3. It compares two different retrieval-store approaches

OpenSearch, with HNSW indexing, and PostgreSQL with pgvector, using an IVF index in this experiment, represent different operational trade-offs.

Neither is automatically 'better.'

Choose based on data size, filtering requirements, query patterns, operational expertise, recall targets, costs, and workload isolation—not benchmark headlines alone.

## Where the experiment stops and production engineering starts

This is **an ingestion and vector-store experiment**, not a complete architecture for document governance, secure multitenancy, and reliable knowledge updates. That distinction matters.

### Missing gate #1: Incremental ingestion and deletes

Large batch ingestion is one problem. Keeping the knowledge base correct on Tuesday after someone changes a document on Monday is another.

A practical ingestion contract should include:

```json
{
  "tenant_id": "tenant-123",
  "document_id": "policy-456",
  "source_version": "v7",
  "content_hash": "sha256:...",
  "embedding_model_version": "model-v2",
  "ingestion_job_id": "job-789"
}
```

Then support **create, update, delete, reprocess, and rollback**.

I would build immutable document versions and publish new chunk sets atomically, or with a controlled cutover. Otherwise, retrieval can mix old and new policy text.

### Missing gate #2: Idempotency and durable recovery

Retries happen. Batch workers crash. Network calls time out *after* the downstream index accepted the write.

A job needs a stable idempotency key, deterministic chunk identifiers, persisted checkpoints, retry limits, and a dead-letter or quarantine path for poison documents.

For example:

```text
chunk_id = hash(tenant_id, document_id, source_version, chunk_index, pipeline_version)
```

Use upserts where supported, and track when a version is fully indexed before making it queryable.

**At-least-once delivery plus idempotent writes** is generally a much safer engineering target than pretending a distributed pipeline will execute each step exactly once.

### Missing gate #3: Document-level authorization

A vector's nearest neighbor is not necessarily an authorized neighbor.

In a multi-tenant system, filters must be enforced in trusted server-side retrieval logic and backed by access-control checks. Never trust a tenant ID supplied directly by the browser.

Authorization is more nuanced than a single tenant field: some documents can be department-restricted, user-specific, or revoked. Search-result filtering, index separation, and post-retrieval verification may all be required depending on the threat model.

### Missing gate #4: Retrieval quality, not merely query speed

A fast result can be the wrong result.

Measure at least:

- **Recall@k and nDCG** against a curated query set.
- **Authorization leakage rate** across tenants and roles.
- **Freshness lag** between source updates and searchable publication.
- **Grounded answer quality**, with citations to source versions.
- **Unanswerable-question handling** and abstention behavior.
- **p50/p95 latency** and cost per successful grounded answer.

An ANN benchmark tells you something about vector search. It does not, by itself, tell you whether your RAG assistant gives trustworthy answers.

### Missing gate #5: Safe secrets and workload identities

The 2024 AWS post discusses credential-expiry troubleshooting and a workaround involving long-lived IAM user keys. I would not carry that workaround into production.

Prefer short-lived, role-based workload credentials, least-privilege policies, isolated network access, and audited operations. Legacy benchmark instructions should be reviewed against current security practices before deployment.

## The architecture I would ship

```text
Approved sources (PDF, web, CMS, CRM, object storage)
                        ↓
              Source connector / CDC
                        ↓
        Raw object + immutable document version
                        ↓
       Durable job queue + idempotency ledger
                        ↓
      Parse / OCR / validate / malware scanning
                        ↓
        PII classification + ACL extraction
                        ↓
           Structure-aware chunking
                        ↓
          Versioned embedding workers
                        ↓
      Staging index + retrieval evaluation
                        ↓
          Atomic publish / index cutover
                        ↓
      Tenant- and role-scoped query service
                        ↓
       Retrieval + reranking + citations
                        ↓
           Guarded LLM response
```

**Keep three distinct concerns separate:**

1. **System of record:** original files, metadata, identities, ACLs, document versions, audit history.
2. **Processing plane:** queues, workers, OCR, chunking, embedding, retries, backfills.
3. **Serving plane:** published searchable chunks, tenant-scoped retrieval, reranking, response generation.

A vector database is a **derived index**, not your only copy of the business's knowledge.

## When Ray is—and isn't—the right choice

Ray can be very appropriate when millions of documents or heavy batch embedding jobs justify distributed GPU scheduling.

But for a knowledge base with thousands of documents, starting with a five-node GPU cluster may be unnecessary complexity. A queue, a small worker pool, object storage, and pgvector may be a much better operational choice.

**Scale from observed bottlenecks.** First measure parse throughput, embedding time, write throughput, index-build time, and p95 retrieval latency. Then optimize the expensive stage.

## PostgreSQL + pgvector or OpenSearch?

My decision framework:

| Requirement | Often start with |
| --- | --- |
| Existing relational app, moderate corpus, transactional metadata | PostgreSQL + pgvector |
| Strong text-search needs, specialized search operations, large search workloads | OpenSearch |
| Strict tenant permissions | Either, with enforced authorization architecture |
| Frequent updates and backfills | Benchmark both against your actual workload |
| Lowest operational complexity | Whichever your team can operate reliably |

This is guidance, not a performance ranking. Index algorithm, filtering strategy, corpus distribution, and infrastructure can change the result substantially.

## A pre-launch checklist for RAG ingestion

Before declaring the system production-ready, I would ask:

- Can we safely retry every ingestion stage without duplicate published chunks?
- Can we delete or revoke a document and prove it is no longer retrievable?
- Can we roll back a broken embedding-model or chunking release?
- Can we demonstrate zero cross-tenant retrieval in adversarial tests?
- Can we trace each answer back to a specific source and version?
- Can we quantify freshness lag, relevance, p95 latency, and cost?
- Can a failed batch recover without manual database surgery?

If the answer to these is 'not yet,' more embedding throughput will not solve the real reliability problem.

## Final thought

AWS's Ray-based ingestion experiment is a valuable reference for the **scale mechanics** of RAG: bulk data preparation, parallel GPU embeddings, vector-store configuration, and ingestion observability.

My extension is simple:

> **A scalable RAG pipeline gets knowledge into an index. A production RAG platform ensures the right knowledge gets there, stays current, remains authorized, and can be recovered when things fail.**

That is the architectural shift worth making.

**Reference:** [AWS Big Data Blog — Build a RAG data ingestion pipeline for large-scale ML workloads (March 13, 2024)](https://aws.amazon.com/blogs/big-data/build-a-rag-data-ingestion-pipeline-for-large-scale-ml-workloads/). AWS configurations and dataset counts cited above come from that article; the reliability and security recommendations are my analysis.

---

## About the Author

I write about software architecture, AI, automation, and real-world engineering challenges.

Explore more of my work and technical insights at [sanukhan.dev](https://sanukhan.dev/).

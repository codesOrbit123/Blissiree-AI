# AI Cost Strategy

Use Flash-Lite for analysis and Flash for user-facing language. Keep prompts concise, bound retrieval, cap output, disable extended thinking, and cache static embeddings. Cloud Run uses CPU only with bounded concurrency and instances. Safe logs omit raw conversation text.

A warm instance improves latency but creates baseline Cloud Run cost. Budgets alert but do not automatically stop spend.

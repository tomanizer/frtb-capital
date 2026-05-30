# csr_nonsec_delta_v1

Synthetic replay bundle for Basel MAR21 CSR non-securitisation delta capital.

Covers:

- MAR21.51 bucket assignment for IG sector buckets 4, 5, 6 and other-sector bucket 16;
- MAR21.53 uniform bucket risk weights (Table 4);
- MAR21.54 intra-bucket name, tenor, and bond/CDS basis correlations;
- MAR21.56 absolute-weight aggregation for bucket 16;
- MAR21.57 inter-bucket gamma across buckets 4, 5, 6, and 16 (Table 5);
- MAR21.6/MAR21.7 correlation scenarios with HIGH selected.

Invalid cases cover unsupported basis risk factors, invalid buckets/tenors, and
missing issuer qualifiers.

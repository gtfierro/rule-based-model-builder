# Rule-Based Model Builder

- `rows.json` contains the IR for Soda Hall:
    - key-value document corresponding to an entity
    - the "key" is a kind of tag
    - the "value" is an identifier, or something specific to the entity
- `template_mappings.py` contains the rules:
    - rules operate on documents and add triples that are implied by the content of the documents
- output: `soda_hall.ttl`

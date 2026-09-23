# LLMorch — Post-Discovery Correlation Engine Specification

## 1. Goal
The `FindingCorrelator` (`correlation/engine.py`) takes raw normalized `TaskResult` outputs and `Evidence` records from two independent agent runs and groups them into `FindingCluster` objects.

## 2. Relationships
- **DUPLICATE**: Identical normalized hypothesis and matching affected file locations.
- **CONTRADICTORY**: One agent claims a vulnerability while the other explicitly negates it for the same file/component.
- **RELATED**: Overlapping file locations or matching vulnerability keywords.
- **INDEPENDENT**: Non-overlapping hypotheses and distinct target locations.

## 3. Principles
- **No Majority Voting**: Correlator does NOT confirm findings based on agent consensus.
- **Provenance Preservation**: Retains exact agent IDs, run IDs, and evidence hashes for each lineage within the cluster.

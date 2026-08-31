"""SFH2.2-A2 independent semantic audit package.

The package is deliberately isolated from the production SFH2 pipeline.  It
reuses the frozen A1 Primary evidence cache, runs an independent semantic
pass, compares structured hypotheses, and materializes only candidate-only
results.
"""

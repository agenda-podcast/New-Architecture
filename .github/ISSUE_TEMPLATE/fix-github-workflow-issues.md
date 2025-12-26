### Task: Fixing GitHub Actions Workflow Failures

#### Related Workflow Run:
[GitHub Actions Workflow Log](https://github.com/agenda-podcast/podcast-maker/actions/runs/20337745485/job/58428925316)

---

### Description

The current GitHub Actions job is experiencing failures. This task includes the following requirements to resolve the issues and improve the pipeline:

1. **Fix Missing Dependencies**:
   - Ensure all dependencies required for the pipeline are properly installed before the workflow begins.
2. **Address Segmentations and Modes**:
   - Debug and correct all segmentation issues that cause instabilities in the pipeline.
   - Provide support for toggling between `segmenting` and `single run` modes.
3. **Set 'Single Run' as Default**:
   - Make `single run` the default mode for easier development and testing.
4. **Documentation**:
   - Update the documentation to include instructions on switching between modes.

---

### What Needs To Be Done

1. Analyze the failing workflow log in the linked job's log.
2. Install and validate any missing dependencies by modifying the CI configuration (e.g., `.github/workflows/*` or other scripts).
3. Add support for both `segmenting` and `single run` modes, ensuring `single run` is the default configuration.
4. Enhance the unit/integration tests to cover and validate both operation modes.

---

### Acceptance Criteria

- All GitHub Actions pipelines complete successfully.
- Verified that no dependencies are missing in the setup process.
- The `single run` mode is set as default.
- Both `segmenting` and `single run` modes operate as intended.
- Documentation is up-to-date and provides essential information on toggling modes.
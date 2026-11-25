"""
tests/test_swe_agent_runner.py
Tests the Autonomous SWE Agent harness and self-correcting trajectory logging.
"""

import os
import tempfile
from imf.cli.agent_runner import SWEAgentRunner


def test_swe_agent_runner_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = SWEAgentRunner(workspace_dir=tmpdir)
        # Run a trivial passing command
        ok = agent.diagnose_and_repair(["python", "-c", "assert 1 + 1 == 2"])
        assert ok is True

        traj_file = os.path.join(tmpdir, "trajectory.json")
        agent.save_trajectory(traj_file)
        assert os.path.exists(traj_file)
        assert len(agent.trajectory) >= 2

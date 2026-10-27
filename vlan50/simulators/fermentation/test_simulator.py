import unittest

from simulator import CHALLENGE_CONFIRM_SAMPLES, FermentationSimulator


class FermentationChallengeTests(unittest.TestCase):
    def setUp(self):
        self.sim = FermentationSimulator("test-fermentation")
        self.sim.interval = 2
        self.sim._tick = 21
        self.sim._t1_glycol_seen_on = True
        self.sim.tanks[0]["temp"] = 21.5
        self.sim.coil_states.update({0: False, 40: False})

    def test_unavailable_coil_read_is_unknown(self):
        self.assertIsNone(self.sim.read_coil(0))

    def test_control_band_does_not_start_confirmation(self):
        self.sim.coil_read_valid.update({0: True, 40: True})
        for _ in range(CHALLENGE_CONFIRM_SAMPLES + 2):
            self.sim.tanks[0]["temp"] = 20.6
            self.sim.step()
        self.assertFalse(self.sim._challenge_latched)
        self.assertEqual(0, self.sim._challenge_condition_samples)

    def test_exact_threshold_is_not_above_threshold(self):
        self.sim.coil_read_valid.update({0: True, 40: True})
        self.sim.tanks[0]["temp"] = 21.0
        self.sim.step()
        self.assertEqual(0, self.sim._challenge_condition_samples)

    def test_failed_read_cannot_trigger_challenge(self):
        self.sim.coil_read_valid.update({0: False, 40: True})

        for _ in range(CHALLENGE_CONFIRM_SAMPLES + 2):
            self.sim.step()

        self.assertFalse(self.sim._challenge_latched)
        self.assertEqual(0, self.sim._challenge_condition_samples)

    def test_five_consecutive_valid_samples_trigger_challenge(self):
        self.sim.coil_read_valid.update({0: True, 40: True})

        for _ in range(CHALLENGE_CONFIRM_SAMPLES - 1):
            self.sim.step()
        self.assertFalse(self.sim._challenge_latched)

        self.sim.step()
        self.assertTrue(self.sim._challenge_latched)
        self.assertEqual(202, self.sim._challenge_reason)

    def test_invalid_sample_resets_pending_confirmation(self):
        self.sim.coil_read_valid.update({0: True, 40: True})
        for _ in range(CHALLENGE_CONFIRM_SAMPLES - 1):
            self.sim.step()

        self.sim.coil_read_valid[0] = False
        self.sim.step()
        self.assertEqual(0, self.sim._challenge_condition_samples)

        self.sim.coil_read_valid[0] = True
        for _ in range(CHALLENGE_CONFIRM_SAMPLES - 1):
            self.sim.step()
        self.assertFalse(self.sim._challenge_latched)


if __name__ == "__main__":
    unittest.main()

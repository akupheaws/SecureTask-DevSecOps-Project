import json
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from release_review import (
    check_production_gate,
    required_reviewers,
    staging_summary,
    deployment_summary,
    validate_release,
)

URL = "http://securetask-staging-example.us-east-1.elb.amazonaws.com"
IMAGE = "123456789012.dkr.ecr.us-east-1.amazonaws.com/securetask@sha256:" + "a" * 64


class ReleaseReviewTests(unittest.TestCase):
    def test_production_without_required_reviewer_fails_closed(self):
        for info in [
            {},
            {"protection_rules": [{"type": "wait_timer"}]},
            {"protection_rules": [{"type": "required_reviewers", "reviewers": []}]},
        ]:
            with self.subTest(info=info), self.assertRaises(ValueError):
                required_reviewers(info)

    def test_user_and_team_reviewers_are_recognized(self):
        info = {
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "reviewers": [
                        {"type": "User", "reviewer": {"id": 1, "login": "reviewer"}},
                        {"type": "Team", "reviewer": {"id": 2, "name": "Release team"}},
                    ],
                }
            ]
        }
        self.assertEqual(required_reviewers(info), ["reviewer", "Release team"])

    def test_gate_check_only_reads_environment_settings(self):
        class Result:
            returncode = 0
            stdout = json.dumps(
                {
                    "protection_rules": [
                        {
                            "type": "required_reviewers",
                            "reviewers": [{"reviewer": {"id": 1, "login": "reviewer"}}],
                        }
                    ]
                }
            )

        with patch("release_review.subprocess.run", return_value=Result()) as run:
            self.assertEqual(check_production_gate("owner/repo"), ["reviewer"])
        self.assertEqual(
            run.call_args.args[0],
            ["gh", "api", "repos/owner/repo/environments/production"],
        )

    def test_environment_api_error_does_not_allow_promotion(self):
        class Result:
            returncode = 1
            stderr = "HTTP 403"

        with patch("release_review.subprocess.run", return_value=Result()):
            with self.assertRaises(RuntimeError):
                check_production_gate("owner/repo")

    def test_review_summary_links_staging_and_the_exact_image(self):
        text = staging_summary(URL, IMAGE, ["reviewer"])
        self.assertIn("](" + URL + ")", text)
        self.assertIn(IMAGE, text)
        self.assertIn("Review deployments", text)
        self.assertIn("Approve and deploy", text)
        self.assertIn("Reject", text)

    def test_invalid_url_or_mutable_image_cannot_be_presented_for_review(self):
        for url, image in [
            ("javascript:alert(1)", IMAGE),
            (URL + "\nInjected", IMAGE),
            (URL, "repository:latest"),
        ]:
            with self.subTest(url=url, image=image), self.assertRaises(ValueError):
                validate_release(url, image)

    def test_staging_and_production_summaries_preserve_digest(self):
        for environment in ["staging", "production"]:
            text = deployment_summary(environment, URL, IMAGE)
            self.assertIn(IMAGE, text)
        self.assertIn("production waits", deployment_summary("staging", URL, IMAGE))


if __name__ == "__main__":
    unittest.main()

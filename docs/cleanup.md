# AWS cleanup confirmation

Cleanup completed on October 11, 2026, in `us-east-1`, following the request for a source-only handoff.

Both application Terraform roots, the platform root, and the bootstrap root were destroyed. The registry images, versioned state objects, project logs, and Dojo secrets were removed. The Dojo EC2 root EBS volume was independently verified as deleted. No final database snapshots were retained.

## Final AWS checks

| Project resource | Remaining count |
| --- | ---: |
| VPC | 0 |
| NAT gateways | 0 |
| Elastic IPs | 0 |
| Load balancers | 0 |
| RDS instances | 0 |
| RDS snapshots | 0 |
| Retained RDS backups | 0 |
| ECR repositories | 0 |
| State buckets | 0 |
| Project IAM roles | 0 |
| Runtime boundary policies | 0 |
| Project log groups | 0 |
| Active project secrets | 0 |
| Nonterminated Dojo instances | 0 |
| Active ECS clusters | 0 |
| Active ECS task definitions | 0 |

Inactive/deleted AWS metadata can remain visible temporarily while AWS completes its internal cleanup. Previously incurred usage charges can still appear on the bill; deletion does not reverse those charges. Shared AWS service-linked roles and resources from unrelated projects were left untouched.

The old application endpoints are no longer usable. Follow [deploy-yourself.md](deploy-yourself.md) to deploy your own copy. The source ZIP excludes credentials, local configuration, Terraform state, database data, and Git history.

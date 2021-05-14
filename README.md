# terraform-aws-manual-scaler

For when autoscaling doesn't cut it

## Example

```terraform
module "manual_scaler" {
  source      = "git@github.com:kabisa/terraform-aws-manual-scaler.git?ref=0.1.0"
  account_id  = var.account_id
  asg         = "eks-f6bc4178-64b2-e25a-23c3-5bdb5e7e19e8"
  domain_name = "blomsma-haltebeheer.nl"
  subdomain   = "scale-knopje"
  region      = var.region
}
```
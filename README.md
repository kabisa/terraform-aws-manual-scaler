# terraform-aws-manual-scaler

For when autoscaling doesn't cut it

## Example

```terraform
module "manual_scaler" {
  source      = "git@github.com:kabisa/terraform-aws-manual-scaler.git?ref=0.1.0"
  account_id  = var.account_id
  asg         = "eks-f6bc4178-64b2-e25a-23c3-5bdb5e7e19e8"
  domain_name = "example.com"
  subdomain   = "scale-button"
  region      = var.region
}
```

### Development

In the Code folder you can use the Pipfile to install the required libs.

Requirements:
- Pipenv
```bash
pip install pipenv
# or
# brew install pipenv 
```
- Docker

With the `pipenv install` command you can then install all dependencies on your machine
These dependencies will be used to build the Lambda zip

Building:
```bash
cd code
pipenv install
./build.sh
```
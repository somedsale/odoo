# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import boto3
from botocore.exceptions import ClientError
PARAMS = {
    "enabled": "somed_s3.enabled",
    "bucket": "somed_s3.bucket",
    "region": "somed_s3.region",
    "access_key": "somed_s3.access_key",
    "secret_key": "somed_s3.secret_key",
    "endpoint_url": "somed_s3.endpoint_url",
    "prefix": "somed_s3.prefix",
    "acl": "somed_s3.acl",
    "use_presigned": "somed_s3.use_presigned",
    "presigned_exp": "somed_s3.presigned_exp",
}

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    somed_s3_enabled = fields.Boolean("Kích hoạt S3")
    somed_s3_bucket = fields.Char("Bucket")
    somed_s3_region = fields.Char("Region")
    somed_s3_access_key = fields.Char("Access Key ID")
    somed_s3_secret_key = fields.Char("Secret Access Key")  # field có password trong view
    somed_s3_endpoint_url = fields.Char("Endpoint URL (tùy chọn)")
    somed_s3_prefix = fields.Char("Đường dẫn Prefix")
    somed_s3_acl = fields.Selection(
        [("private", "private"), ("public-read", "public-read")],
        string="ACL",
        default="private",
    )
    somed_s3_use_presigned = fields.Boolean("Dùng presigned URL khi xem/tải")
    somed_s3_presigned_exp = fields.Integer("Thời gian presigned (giây)", default=300)

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(PARAMS["enabled"], "1" if self.somed_s3_enabled else "0")
        ICP.set_param(PARAMS["bucket"], self.somed_s3_bucket or "")
        ICP.set_param(PARAMS["region"], self.somed_s3_region or "")
        ICP.set_param(PARAMS["access_key"], self.somed_s3_access_key or "")
        # ❗ Odoo 17: KHÔNG có tham số groups cho set_param
        if self.somed_s3_secret_key:
            ICP.set_param(PARAMS["secret_key"], self.somed_s3_secret_key)
        ICP.set_param(PARAMS["endpoint_url"], self.somed_s3_endpoint_url or "")
        ICP.set_param(PARAMS["prefix"], (self.somed_s3_prefix or ""))
        ICP.set_param(PARAMS["acl"], self.somed_s3_acl or "private")
        ICP.set_param(PARAMS["use_presigned"], "1" if self.somed_s3_use_presigned else "0")
        ICP.set_param(PARAMS["presigned_exp"], str(self.somed_s3_presigned_exp or 300))

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            somed_s3_enabled = ICP.get_param(PARAMS["enabled"]) == "1",
            somed_s3_bucket = ICP.get_param(PARAMS["bucket"]),
            somed_s3_region = ICP.get_param(PARAMS["region"]),
            somed_s3_access_key = ICP.get_param(PARAMS["access_key"]),
            # ❗ Không trả secret ra UI để tránh lộ; người dùng cần nhập lại nếu muốn đổi
            somed_s3_secret_key = False,
            somed_s3_endpoint_url = ICP.get_param(PARAMS["endpoint_url"]),
            somed_s3_prefix = ICP.get_param(PARAMS["prefix"]),
            somed_s3_acl = ICP.get_param(PARAMS["acl"]) or "private",
            somed_s3_use_presigned = ICP.get_param(PARAMS["use_presigned"]) == "1",
            somed_s3_presigned_exp = int(ICP.get_param(PARAMS["presigned_exp"]) or "300"),
        )
        return res
    def action_test_s3_connection(self):
        """Nút Test Connection"""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        bucket = ICP.get_param("somed_s3.bucket")
        region = ICP.get_param("somed_s3.region")
        access_key = ICP.get_param("somed_s3.access_key")
        secret_key = ICP.get_param("somed_s3.secret_key")
        endpoint_url = ICP.get_param("somed_s3.endpoint_url") or None

        if not (bucket and access_key and secret_key):
            raise UserError("Chưa cấu hình đầy đủ Bucket / Access / Secret Key.")

        import boto3
        from botocore.exceptions import ClientError
        try:
            session = boto3.session.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region or None,
            )
            s3 = session.client("s3", endpoint_url=endpoint_url)
            s3.head_bucket(Bucket=bucket)
            test_key = "odoo_test_connection.txt"
            s3.put_object(Bucket=bucket, Key=test_key, Body=b"Odoo S3 connection test")
            s3.delete_object(Bucket=bucket, Key=test_key)
        except ClientError as e:
            raise UserError(f"Lỗi S3: {e.response['Error']['Message']}")
        except Exception as e:
            raise UserError(f"Lỗi khác: {str(e)}")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "✅ Kết nối S3 thành công",
                "message": f"Bucket '{bucket}' sẵn sàng sử dụng.",
                "sticky": False,
                "type": "success",
            },
        }
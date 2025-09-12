from odoo import models, api

class DepartmentManager(models.Model):
    _inherit = 'hr.department'  # Kế thừa model hr.department

    @api.model
    def get_manager_id_by_name(self, department_name):
        """
        Hàm lấy ID của quản lý phòng ban dựa trên tên phòng ban.
        :param department_name: Tên phòng ban (chuỗi)
        :return: ID của quản lý (integer) hoặc False nếu không tìm thấy
        """
        department = self.search([('name', '=', department_name)], limit=1)
        if department and department.manager_id:
            return department.manager_id
        return False
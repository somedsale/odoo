import base64
import io
import random
from PIL import Image, ImageDraw, ImageFont
from odoo import models, api, tools

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Material Design Color Palette (500 weight)
    _avatar_colors = [
        '#F44336', '#E91E63', '#9C27B0', '#673AB7', '#3F51B5',
        '#2196F3', '#03A9F4', '#00BCD4', '#009688', '#4CAF50',
        '#8BC34A', '#CDDC39', '#FFC107', '#FF9800', '#FF5722',
        '#795548', '#607D8B', '#FB8C00', '#D81B60', '#8E24AA'
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.image_1920:
                record._generate_avatar()
        return records

    def write(self, vals):
        res = super().write(vals)
        # If image is cleared or name changed while having no image
        # Note: 'image_1920' False means it's being cleared.
        if 'image_1920' in vals and not vals['image_1920']:
             # If manually cleared, maybe we shouldn't regenerate immediately? 
             # Actually, the user requirement is "for who don't have an image". 
             # Let's regenerate to avoid ugly placeholders.
             for record in self:
                 record._generate_avatar()
        return res

    def _generate_avatar(self):
        """ Generates an avatar with initials and saves it to image_1920 """
        self.ensure_one()
        if not self.name:
            return

        # 1. Calculate Initials
        name_parts = self.name.strip().split()
        initials = ""
        if len(name_parts) == 1:
            initials = name_parts[0][:2].upper()
        elif len(name_parts) >= 2:
            initials = name_parts[0][0].upper() + name_parts[1][0].upper()
        else:
            initials = "??"

        # 2. Pick Color based on name hash
        # Use simple sum of char codes to pick index
        char_sum = sum(ord(c) for c in self.name)
        bg_color = self._avatar_colors[char_sum % len(self._avatar_colors)]
        
        # 3. Generate Image
        size = 256
        image = Image.new('RGB', (size, size), color=bg_color)
        draw = ImageDraw.Draw(image)
        
        # Try to load a font, fallback to default
        try:
            # Linux standard font path, or Odoo's bundled fonts if accessible. 
            # DejavuSans-Bold is usually safe on Linux servers.
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(size/2.5))
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", int(size/2.5))
            except OSError:
                font = ImageFont.load_default()

        # Center Text
        # getbbox returns (left, top, right, bottom)
        bbox = draw.textbbox((0, 0), initials, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Calculate position to center
        x = (size - text_width) / 2 - bbox[0]
        y = (size - text_height) / 2 - bbox[1]

        draw.text((x, y), initials, fill='white', font=font)

        # 4. Save to buffer
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        
        # 5. Write to record (bypass write override to avoid recursion loops if carefully handled, 
        # but here we are calling write('image_1920') which triggers write.
        # However, our write override checks 'if not vals[image]', so writing WITH image won't trigger regen.
        self.write({'image_1920': base64.b64encode(buffer.getvalue())})

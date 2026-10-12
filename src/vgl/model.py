"""The base VGL model every dialect builds on."""

from pydantic import BaseModel, Field


class ObjectDescription(BaseModel):
    description: str = Field(..., description="Short description of the object.")
    location: str = Field(..., description="E.g., 'center', 'top-left', 'bottom-right foreground'.")
    relationship: str = Field(..., description="Describe the relationship between the object and the other objects in the image.")
    relative_size: str | None = Field(None, description="E.g., 'small', 'medium', 'large within frame'.")
    shape_and_color: str | None = Field(None, description="Describe the basic shape and dominant color.")
    texture: str | None = Field(None, description="E.g., 'smooth', 'rough', 'metallic', 'furry'.")
    appearance_details: str | None = Field(None, description="Any other notable visual details.")
    number_of_objects: int | None = Field(None, description="The number of objects in the cluster.")
    pose: str | None = Field(None, description="Describe the body position.")
    expression: str | None = Field(None, description="Describe facial expression.")
    clothing: str | None = Field(None, description="Describe attire.")
    action: str | None = Field(None, description="Describe the action of the human.")
    gender: str | None = Field(None, description="Describe the gender of the human.")
    skin_tone_and_texture: str | None = Field(None, description="Describe the skin tone and texture.")
    orientation: str | None = Field(None, description="Describe the orientation of the human.")


class LightingDetails(BaseModel):
    conditions: str = Field(..., description="E.g., 'bright daylight', 'dim indoor', 'studio lighting', 'golden hour'.")
    direction: str = Field(..., description="E.g., 'front-lit', 'backlit', 'side-lit from left'.")
    shadows: str | None = Field(None, description="Describe the presence of shadows.")


class AestheticsDetails(BaseModel):
    composition: str = Field(..., description="E.g., 'rule of thirds', 'symmetrical', 'centered', 'leading lines'.")
    color_scheme: str = Field(..., description="E.g., 'monochromatic blue', 'warm complementary colors', 'high contrast'.")
    mood_atmosphere: str = Field(..., description="E.g., 'serene', 'energetic', 'mysterious', 'joyful'.")


class PhotographicCharacteristicsDetails(BaseModel):
    depth_of_field: str = Field(..., description="E.g., 'shallow', 'deep', 'bokeh background'.")
    focus: str = Field(..., description="E.g., 'sharp focus on subject', 'soft focus', 'motion blur'.")
    camera_angle: str = Field(..., description="E.g., 'eye-level', 'low angle', 'high angle', 'dutch angle'.")
    lens_focal_length: str = Field(..., description="E.g., 'wide-angle', 'telephoto', 'macro', 'fisheye'.")


class TextRender(BaseModel):
    text: str = Field(..., description="The text content.")
    location: str = Field(..., description="E.g., 'center', 'top-left', 'bottom-right foreground'.")
    size: str = Field(..., description="E.g., 'small', 'medium', 'large within frame'.")
    color: str = Field(..., description="E.g., 'red', 'blue', 'green'.")
    font: str = Field(..., description="E.g., 'realistic', 'cartoonish', 'minimalist'.")
    appearance_details: str | None = Field(None, description="Any other notable visual details.")


class VGL(BaseModel):
    """Fields every dialect shares. A dialect subclasses this to add its own."""

    short_description: str = Field(..., description="A concise summary of the image content, 200 words maximum.")
    objects: list[ObjectDescription] | None = Field(None, description="List of prominent foreground/midground objects.")
    background_setting: str = Field(..., description="Describe the overall environment, setting, or background, including any notable background elements.")
    lighting: LightingDetails = Field(..., description="Details about the lighting.")
    aesthetics: AestheticsDetails = Field(..., description="Details about the image aesthetics.")
    photographic_characteristics: PhotographicCharacteristicsDetails | None = Field(None, description="Details about photographic characteristics.")
    style_medium: str | None = Field(None, description="Identify the artistic style or medium.")
    text_render: list[TextRender] | None = Field(None, description="List of text renders in the image.")
    context: str = Field(..., description="Provide any additional context that helps understand the image better.")
    artistic_style: str | None = Field(None, description="Describe specific artistic characteristics, 3 words maximum.")

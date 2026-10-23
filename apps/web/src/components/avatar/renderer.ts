import type { AvatarParams } from "@/lib/avatar";

/**
 * Anything that can draw the avatar from a frame of params. SvgFace is the
 * placeholder; a Live2D renderer would implement this by calling
 * model.setParameterValueById(id, value) for each param.
 */
export interface AvatarRenderer {
  render(params: AvatarParams): void;
}

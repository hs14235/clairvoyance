"use client";

import { Ref, useImperativeHandle, useRef } from "react";

import type { AvatarParams } from "@/lib/avatar";
import type { AvatarRenderer } from "./renderer";

const SKIN = "#f3d9c6";
const HAIR = "#4a3b4f";
const SHIRT = "#7d9cb8";
const INK = "#3a2f35";

function mouthPath(form: number, open: number) {
  const corner = -5 * form;
  const upper = 5 * form - 2 * open;
  const lower = upper + 2 + open * 22;
  return `M-15 ${corner} Q0 ${upper} 15 ${corner} Q0 ${lower} -15 ${corner} Z`;
}

function eyeMarkup(
  x: number,
  g: Ref<SVGGElement>,
  pupil: Ref<SVGCircleElement>,
  lid: Ref<SVGPathElement>,
) {
  return (
    <>
      <g ref={g} transform={`translate(${x} 102)`}>
        <ellipse rx="9" ry="7.5" fill="#fff" />
        <circle ref={pupil} r="4.5" fill={INK} />
      </g>
      {/* Closed-eye line, shown when the eye is nearly shut. */}
      <path
        ref={lid}
        d={`M${x - 9} 102 Q${x} 106 ${x + 9} 102`}
        stroke={INK}
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
        opacity="0"
      />
    </>
  );
}

/** Placeholder 2D face driven directly by Live2D-style params. */
export default function SvgFace({ ref }: { ref?: Ref<AvatarRenderer> }) {
  const body = useRef<SVGGElement>(null);
  const head = useRef<SVGGElement>(null);
  const features = useRef<SVGGElement>(null);
  const eyeL = useRef<SVGGElement>(null);
  const eyeR = useRef<SVGGElement>(null);
  const pupilL = useRef<SVGCircleElement>(null);
  const pupilR = useRef<SVGCircleElement>(null);
  const lidL = useRef<SVGPathElement>(null);
  const lidR = useRef<SVGPathElement>(null);
  const browL = useRef<SVGGElement>(null);
  const browR = useRef<SVGGElement>(null);
  const mouth = useRef<SVGPathElement>(null);
  const cheeks = useRef<SVGGElement>(null);

  useImperativeHandle(ref, () => ({
    render(p: AvatarParams) {
      const set = (el: Element | null, attr: string, value: string) =>
        el?.setAttribute(attr, value);

      set(body.current, "transform",
        `translate(0 ${-2 * p.ParamBreath}) rotate(${p.ParamBodyAngleX} 100 230)`);
      set(head.current, "transform",
        `translate(${p.ParamBodyAngleX * 1.5} ${-2 * p.ParamBreath}) rotate(${p.ParamAngleZ} 100 150)`);
      // Fake 3D: features slide toward the direction the head turns.
      set(features.current, "transform",
        `translate(${p.ParamAngleX * 0.5} ${-p.ParamAngleY * 0.4})`);

      const eye = (
        g: SVGGElement | null,
        pupil: SVGCircleElement | null,
        lid: SVGPathElement | null,
        x: number,
        open: number,
      ) => {
        set(g, "transform", `translate(${x} 102) scale(1 ${Math.max(open, 0.02)})`);
        set(pupil, "cx", String(p.ParamEyeBallX * 4));
        set(pupil, "cy", String(-p.ParamEyeBallY * 3));
        set(lid, "opacity", open < 0.3 ? "1" : "0");
      };
      eye(eyeL.current, pupilL.current, lidL.current, 80, p.ParamEyeLOpen);
      eye(eyeR.current, pupilR.current, lidR.current, 120, p.ParamEyeROpen);

      // Brow angle +1 raises the inner (centre-facing) end.
      set(browL.current, "transform",
        `translate(80 ${87 - p.ParamBrowLY * 5}) rotate(${-p.ParamBrowLAngle * 22})`);
      set(browR.current, "transform",
        `translate(120 ${87 - p.ParamBrowRY * 5}) rotate(${p.ParamBrowRAngle * 22})`);

      set(mouth.current, "d", mouthPath(p.ParamMouthForm, p.ParamMouthOpenY));
      set(cheeks.current, "opacity", String(p.ParamCheek * 0.7));
    },
  }));

  return (
    <svg viewBox="0 0 200 230" width="100%" height="100%" aria-hidden="true">
      <g ref={body}>
        <path d="M28 230 Q30 178 100 172 Q170 178 172 230 Z" fill={SHIRT} />
        <rect x="88" y="145" width="24" height="32" rx="8" fill={SKIN} />
      </g>
      <g ref={head}>
        <ellipse cx="100" cy="92" rx="60" ry="64" fill={HAIR} />
        <ellipse cx="100" cy="100" rx="50" ry="56" fill={SKIN} />
        <g ref={features}>
          <g ref={cheeks} opacity="0">
            <ellipse cx="72" cy="120" rx="9" ry="5" fill="#f2a1a1" />
            <ellipse cx="128" cy="120" rx="9" ry="5" fill="#f2a1a1" />
          </g>
          {eyeMarkup(80, eyeL, pupilL, lidL)}
          {eyeMarkup(120, eyeR, pupilR, lidR)}
          <g ref={browL} transform="translate(80 87)">
            <path d="M-10 1 Q0 -3 10 1" stroke={HAIR} strokeWidth="3" strokeLinecap="round" fill="none" />
          </g>
          <g ref={browR} transform="translate(120 87)">
            <path d="M-10 1 Q0 -3 10 1" stroke={HAIR} strokeWidth="3" strokeLinecap="round" fill="none" />
          </g>
          <g transform="translate(100 136)">
            <path ref={mouth} d={mouthPath(0, 0)} fill="#9c4a55" stroke={INK} strokeWidth="1.5" strokeLinejoin="round" />
          </g>
        </g>
        <path d="M46 84 Q52 36 100 34 Q150 36 154 84 Q128 60 100 64 Q80 58 46 84 Z" fill={HAIR} />
      </g>
    </svg>
  );
}

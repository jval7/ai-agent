import type * as reactModule from "react";

interface FormFieldProps {
  label: string;
  htmlFor: string;
  helperText?: string;
  error?: string;
  children: reactModule.ReactNode;
}

export function FormField(props: FormFieldProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700" htmlFor={props.htmlFor}>
        {props.label}
      </label>
      {props.helperText !== undefined ? (
        <p className="mt-0.5 text-xs text-slate-500">{props.helperText}</p>
      ) : null}
      {props.children}
      {props.error !== undefined ? (
        <p className="mt-1 text-xs text-red-600">{props.error}</p>
      ) : null}
    </div>
  );
}

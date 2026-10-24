/**
 * Adapted from Space UI Empty (MIT), Copyright (c) 2026 Space UI.
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function Empty({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="empty" className={cn("empty-state", className)} {...props} />;
}

export function EmptyHeader({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="empty-header" className={cn("empty-state-header", className)} {...props} />;
}

export function EmptyTitle({ className, ...props }: ComponentProps<"h3">) {
  return <h3 data-slot="empty-title" className={cn("empty-state-title", className)} {...props} />;
}

export function EmptyDescription({ className, ...props }: ComponentProps<"p">) {
  return <p data-slot="empty-description" className={cn("empty-state-description", className)} {...props} />;
}

export function EmptyContent({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="empty-content" className={cn("empty-state-content", className)} {...props} />;
}

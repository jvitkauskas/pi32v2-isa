; SPDX-FileCopyrightText: 2026 Julius Vitkauskas
; SPDX-License-Identifier: MIT-0
; Functions for the code generator test on the FM-1 (tools/llvm/cgtest.py has the inputs and expected results).
target triple = "pi32v2"

define i32 @t_add(i32 %a, i32 %b) nounwind { %r = add i32 %a, %b
  ret i32 %r }
define i32 @t_sub(i32 %a, i32 %b) nounwind { %r = sub i32 %a, %b
  ret i32 %r }
define i32 @t_mul(i32 %a, i32 %b) nounwind { %r = mul i32 %a, %b
  ret i32 %r }
define i32 @t_sdiv(i32 %a, i32 %b) nounwind { %r = sdiv i32 %a, %b
  ret i32 %r }
define i32 @t_udiv(i32 %a, i32 %b) nounwind { %r = udiv i32 %a, %b
  ret i32 %r }
define i32 @t_srem(i32 %a, i32 %b) nounwind { %r = srem i32 %a, %b
  ret i32 %r }
define i32 @t_urem(i32 %a, i32 %b) nounwind { %r = urem i32 %a, %b
  ret i32 %r }
define i32 @t_logic(i32 %a, i32 %b) nounwind {
  %x = and i32 %a, %b
  %y = or i32 %x, 4096
  %z = xor i32 %y, %b
  %w = and i32 %z, 255
  %v = or i32 %w, %a
  ret i32 %v }
define i32 @t_shl(i32 %a, i32 %b) nounwind { %r = shl i32 %a, %b
  ret i32 %r }
define i32 @t_lshr(i32 %a, i32 %b) nounwind { %r = lshr i32 %a, %b
  ret i32 %r }
define i32 @t_ashr(i32 %a, i32 %b) nounwind { %r = ashr i32 %a, %b
  ret i32 %r }
define i32 @t_shimm(i32 %a) nounwind {
  %x = shl i32 %a, 5
  %y = lshr i32 %a, 27
  %z = ashr i32 %a, 3
  %s = add i32 %x, %y
  %r = xor i32 %s, %z
  ret i32 %r }
define i32 @t_const(i32 %a) nounwind {
  %x = add i32 %a, 305419896
  %y = add i32 %x, -8000
  %z = xor i32 %y, -1
  ret i32 %z }

define i32 @t_eq(i32 %a, i32 %b) nounwind { %c = icmp eq i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_ne(i32 %a, i32 %b) nounwind { %c = icmp ne i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_ult(i32 %a, i32 %b) nounwind { %c = icmp ult i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_ule(i32 %a, i32 %b) nounwind { %c = icmp ule i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_ugt(i32 %a, i32 %b) nounwind { %c = icmp ugt i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_uge(i32 %a, i32 %b) nounwind { %c = icmp uge i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_slt(i32 %a, i32 %b) nounwind { %c = icmp slt i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_sle(i32 %a, i32 %b) nounwind { %c = icmp sle i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_sgt(i32 %a, i32 %b) nounwind { %c = icmp sgt i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_sge(i32 %a, i32 %b) nounwind { %c = icmp sge i32 %a, %b
  %r = zext i1 %c to i32
  ret i32 %r }
define i32 @t_max(i32 %a, i32 %b) nounwind {
  %c = icmp sgt i32 %a, %b
  %r = select i1 %c, i32 %a, i32 %b
  ret i32 %r }

@words = global [8 x i32] [i32 1, i32 -2, i32 300, i32 -40000, i32 5, i32 6000000, i32 7, i32 -8]
@bytes = global [8 x i8] [i8 1, i8 -2, i8 127, i8 -128, i8 5, i8 200, i8 7, i8 -8]
@halves = global [4 x i16] [i16 1, i16 -2, i16 32767, i16 -32768]
@counter = global i32 0

define i32 @t_sum_words(i32 %n) nounwind {
entry:
  br label %head
head:
  %i = phi i32 [ 0, %entry ], [ %i1, %body ]
  %s = phi i32 [ 0, %entry ], [ %s1, %body ]
  %c = icmp slt i32 %i, %n
  br i1 %c, label %body, label %done
body:
  %p = getelementptr [8 x i32], ptr @words, i32 0, i32 %i
  %v = load i32, ptr %p
  %s1 = add i32 %s, %v
  %i1 = add i32 %i, 1
  br label %head
done:
  ret i32 %s }
define i32 @t_sbyte(i32 %i) nounwind {
  %p = getelementptr [8 x i8], ptr @bytes, i32 0, i32 %i
  %v = load i8, ptr %p
  %r = sext i8 %v to i32
  ret i32 %r }
define i32 @t_ubyte(i32 %i) nounwind {
  %p = getelementptr [8 x i8], ptr @bytes, i32 0, i32 %i
  %v = load i8, ptr %p
  %r = zext i8 %v to i32
  ret i32 %r }
define i32 @t_shalf(i32 %i) nounwind {
  %p = getelementptr [4 x i16], ptr @halves, i32 0, i32 %i
  %v = load i16, ptr %p
  %r = sext i16 %v to i32
  ret i32 %r }
define i32 @t_uhalf(i32 %i) nounwind {
  %p = getelementptr [4 x i16], ptr @halves, i32 0, i32 %i
  %v = load i16, ptr %p
  %r = zext i16 %v to i32
  ret i32 %r }
; store a byte, a half and a word through pointers, read them back
define i32 @t_stores(i32 %a) nounwind {
  %buf = alloca [4 x i32], align 4
  %w = getelementptr [4 x i32], ptr %buf, i32 0, i32 0
  store i32 0, ptr %w
  %w1 = getelementptr [4 x i32], ptr %buf, i32 0, i32 1
  store i32 0, ptr %w1
  %b = getelementptr i8, ptr %buf, i32 1
  %t8 = trunc i32 %a to i8
  store i8 %t8, ptr %b
  %h = getelementptr i8, ptr %buf, i32 6
  %t16 = trunc i32 %a to i16
  store i16 %t16, ptr %h
  %r0 = load i32, ptr %w
  %r1 = load i32, ptr %w1
  %r = xor i32 %r0, %r1
  ret i32 %r }
define i32 @t_counter(i32 %a) nounwind {
  %v = load i32, ptr @counter
  %n = add i32 %v, %a
  store i32 %n, ptr @counter
  ret i32 %n }

define i32 @t_fib(i32 %n) nounwind {
  %c = icmp ult i32 %n, 2
  br i1 %c, label %base, label %rec
base:
  ret i32 %n
rec:
  %n1 = sub i32 %n, 1
  %n2 = sub i32 %n, 2
  %a = call i32 @t_fib(i32 %n1)
  %b = call i32 @t_fib(i32 %n2)
  %r = add i32 %a, %b
  ret i32 %r }

define i32 @sum6(i32 %a, i32 %b, i32 %c, i32 %d, i32 %e, i32 %f) nounwind noinline {
  %1 = mul i32 %a, 1
  %2 = mul i32 %b, 10
  %3 = mul i32 %c, 100
  %4 = mul i32 %d, 1000
  %5 = mul i32 %e, 10000
  %6 = mul i32 %f, 100000
  %s1 = add i32 %1, %2
  %s2 = add i32 %s1, %3
  %s3 = add i32 %s2, %4
  %s4 = add i32 %s3, %5
  %s5 = add i32 %s4, %6
  ret i32 %s5 }
define i32 @t_call6(i32 %x, i32 %y) nounwind {
  %r = call i32 @sum6(i32 %x, i32 2, i32 3, i32 4, i32 %y, i32 6)
  ret i32 %r }

; many values live across calls: the callee-saved registers
define i32 @t_pressure(i32 %x) nounwind {
  %a = add i32 %x, 1
  %b = add i32 %x, 2
  %c = add i32 %x, 3
  %d = add i32 %x, 4
  %e = add i32 %x, 5
  %f = add i32 %x, 6
  %g = add i32 %x, 7
  %h = add i32 %x, 8
  %i = add i32 %x, 9
  %j = add i32 %x, 10
  %k = add i32 %x, 11
  %l = add i32 %x, 12
  %m = add i32 %x, 13
  %y = call i32 @sum6(i32 %a, i32 %b, i32 %c, i32 %d, i32 %e, i32 %f)
  %s1 = add i32 %y, %g
  %s2 = mul i32 %s1, %h
  %s3 = add i32 %s2, %i
  %s4 = xor i32 %s3, %j
  %s5 = add i32 %s4, %k
  %s6 = sub i32 %s5, %l
  %s7 = add i32 %s6, %m
  ret i32 %s7 }

define i64 @t_add64(i64 %a, i64 %b) nounwind { %r = add i64 %a, %b
  ret i64 %r }
define i64 @t_sub64(i64 %a, i64 %b) nounwind { %r = sub i64 %a, %b
  ret i64 %r }
define i64 @t_shl64(i64 %a) nounwind { %r = shl i64 %a, 13
  ret i64 %r }

define i32 @t_switch(i32 %x) nounwind {
  switch i32 %x, label %d [ i32 0, label %a
                            i32 1, label %b
                            i32 7, label %c ]
a: ret i32 100
b: ret i32 -200
c: ret i32 70000
d: ret i32 9 }

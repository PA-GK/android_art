#!/usr/bin/env python
#
# Copyright (C) 2016 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys, re
from os import listdir
from cStringIO import StringIO

# This file is included verbatim at the start of the in-memory python script.
SCRIPT_SETUP_CODE = "common/gen_setup.py"

INTERP_DEFS_FILE = "../../../libdexfile/dex/dex_instruction_list.h" # need opcode list
NUM_PACKED_OPCODES = 256

# Extract an ordered list of instructions from the VM sources.  We use the
# "goto table" definition macro, which has exactly NUM_PACKED_OPCODES entries.
def getOpcodeList():
  opcodes = []
  opcode_fp = open(INTERP_DEFS_FILE)
  opcode_re = re.compile(r"^\s*V\((....), (\w+),.*", re.DOTALL)
  for line in opcode_fp:
    match = opcode_re.match(line)
    if not match:
      continue
    opcodes.append("op_" + match.group(2).lower())
  opcode_fp.close()

  if len(opcodes) != NUM_PACKED_OPCODES:
    print "ERROR: found %d opcodes in Interp.h (expected %d)" \
        % (len(opcodes), NUM_PACKED_OPCODES)
    raise SyntaxError, "bad opcode count"
  return opcodes

indent_re = re.compile(r"^%( *)")

# Finds variable references in text: $foo or ${foo}
escape_re = re.compile(r'''
  (?<!\$)        # Look-back: must not be preceded by another $.
  \$
  (\{)?          # May be enclosed by { } pair.
  (?P<name>\w+)  # Save the symbol in named group.
  (?(1)\})       # Expect } if and only if { was present.
''', re.VERBOSE)

def generate_script(arch, setup_code):
  # Create new python script and write the initial setup code.
  script = StringIO()  # File-like in-memory buffer.
  script.write("# DO NOT EDIT: This file was generated by gen-mterp.py.\n")
  script.write('arch = "' + arch + '"\n')
  script.write(setup_code)
  opcodes = getOpcodeList()
  script.write("def opcodes(is_alt):\n")
  for i in xrange(NUM_PACKED_OPCODES):
    script.write('  write_opcode({0}, "{1}", {1}, is_alt)\n'.format(i, opcodes[i]))

  # Find all template files and translate them into python code.
  files = listdir(arch)
  for file in sorted(files):
    f = open(arch + "/" + file, "r")
    indent = ""
    for line in f.readlines():
      line = line.rstrip()
      if line.startswith("%"):
        script.write(line.lstrip("%") + "\n")
        indent = indent_re.match(line).group(1)
        if line.endswith(":"):
          indent += "  "
      else:
        line = escape_re.sub(r"''' + \g<name> + '''", line)
        line = line.replace("\\", "\\\\")
        line = line.replace("$$", "$")
        script.write(indent + "write_line('''" + line + "''')\n")
    script.write("\n")
    f.close()

  script.write('generate()\n')
  script.seek(0)
  return script.read()

# Generate the script for each architecture and execute it.
for arch in ["arm", "arm64", "mips", "mips64", "x86", "x86_64"]:
  with open(SCRIPT_SETUP_CODE, "r") as setup_code_file:
    script = generate_script(arch, setup_code_file.read())
  filename = "out/mterp_" + arch + ".py"  # Name to report in error messages.
  # open(filename, "w").write(script)  # Write the script to disk for debugging.
  exec(compile(script, filename, mode='exec'))

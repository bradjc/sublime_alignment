import sublime
import sublime_plugin
import re
import math
import os
import sys

# This is necessary due to load order of packages in Sublime Text 2
sys.path.append(os.path.join(sublime.packages_path(), 'Default'))
indentation = __import__('indentation')
reload(indentation)
del sys.path[-1]

normed_rowcol = indentation.line_and_normed_pt


def convert_to_mid_line_tabs(view, edit, tab_size, pt, length):
    spaces_end = pt + length
    spaces_start = spaces_end
    while view.substr(spaces_start-1) == ' ':
        spaces_start -= 1
    spaces_len = spaces_end - spaces_start
    normed_start = normed_rowcol(view, spaces_start)[1]
    normed_mod = normed_start % tab_size
    tabs_len = 0
    diff = 0
    if normed_mod != 0:
        diff = tab_size - normed_mod
        tabs_len += 1
    tabs_len += int(math.ceil(float(spaces_len - diff)
        / float(tab_size)))
    view.replace(edit, sublime.Region(spaces_start,
        spaces_end), '\t' * tabs_len)
    return tabs_len - spaces_len


class AlignmentCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        sel = view.sel()
        max_col = 0

        settings = view.settings()
        tab_size = int(settings.get('tab_size', 8))
        use_spaces = settings.get('translate_tabs_to_spaces')

        # This handles aligning multiple selections
        if len(sel) > 1:
            max_col = max([normed_rowcol(view, region.b)[1] for region in sel])

            for region in sel:
                length = max_col - normed_rowcol(view, region.b)[1]
                view.insert(edit, region.b, ' ' * length)
                if settings.get('mid_line_tabs') and not use_spaces:
                    convert_to_mid_line_tabs(view, edit, tab_size, region.b,
                        length)
            return
        

        # This handles aligning single multi-line selections
        points = []
        line_nums = [view.rowcol(line.a)[0] for line in view.lines(sel[0])]

        trim_trailing_white_space = \
            settings.get('trim_trailing_white_space_on_save')

        # Indent all selected lines the same distance
        if settings.get('align_indent'):
            # Align the left edges by first finding the left edge
            for row in line_nums:
                pt = view.text_point(row, 0)

                # Skip blank lines when the user trims trailing whitespace
                line = view.line(pt)
                if trim_trailing_white_space and line.a == line.b:
                    continue

                char = view.substr(pt)
                while char == ' ' or char == '\t':
                    # Turn tabs into spaces when the preference is spaces
                    if use_spaces and char == '\t':
                        view.replace(edit, sublime.Region(pt, pt+1), ' ' *
                            tab_size)

                    # Turn spaces into tabs when tabs are the preference
                    if not use_spaces and char == ' ':
                        max_pt = pt + tab_size
                        end_pt = pt
                        while view.substr(end_pt) == ' ' and end_pt < \
                                max_pt:
                            end_pt += 1
                        view.replace(edit, sublime.Region(pt, end_pt),
                            '\t')

                    pt += 1

                    # Rollback if the left edge wraps to the next line
                    if view.rowcol(pt)[0] != row:
                        pt -= 1
                        break

                    char = view.substr(pt)

                points.append(pt)
                max_col = max([max_col, view.rowcol(pt)[1]])

            # Adjust the left edges based on the maximum that was found
            adjustment = 0
            max_length = 0
            for pt in points:
                pt += adjustment
                length = max_col - view.rowcol(pt)[1]
                max_length = max([max_length, length])
                adjustment += length
                view.insert(edit, pt, (' ' if use_spaces else '\t') *
                    length)

            if max_length != 0:
                # I'm not sure why just yet, but stop now
                return
           # perform_mid_line = max_length == 0

   
        # Setup the alignment characters
        alignment_chars        = settings.get('alignment_chars') or []
        alignment_prefix_chars = settings.get('alignment_prefix_chars') or []
        alignment_space_chars  = settings.get('alignment_space_chars') or []

        alignment_pattern = '|'.join([re.escape(ch) for ch in alignment_chars])


        # Check if we want to align variables declarations
        if settings.get('alignment_align_var_defs'):
            # Determine if the selected block is variable declarations or just
            #  variable assignments.
            is_variable_def_block = False
            for ln in line_nums:
                line = view.substr(view.line(view.text_point(ln, 0))) # get current line
                # If there is an assigment character in this line, ignore it
                #  and anything after it.
                l_start = 0
                result  = re.search(alignment_pattern, line)
                l_end   = result.start() if result else len(line)

                # Analyze the remaining line portion.
                words = line[l_start:l_end].split()
                if len(words) < 2:
                    # Only 1 string. Can't define a variable with only 1 string.
                    break
                elif ',' in line[l_start:l_end]:
                    # String contains a comma. This could be either:
                    #  - assignment: a function that returns multiple values
                    #  - definition: templated type, for example
                    continue
                else:
                    # I think if there are multiple strings without commas
                    #  we have a variable definition block.
                    is_variable_def_block = True
                    break

            if is_variable_def_block:
                print "DEF"
                # Add spaces so the last thing before any assignment operators
                #  line up
                spaces = []
                for ln in line_nums:
                    line    = view.substr(view.line(view.text_point(ln, 0)))
                    result  = re.search(alignment_pattern, line)
                    l_start = 0
                    l_end   = result.start() if result else len(line)
                    line    = line[l_start:l_end].rstrip()

                    divide_start = 0
                    divide_end   = 0
                    whitespace = [' ', '\t']
                    for i in range(len(line)-1, -1, -1):
                        if divide_end == 0:
                            if line[i] in whitespace:
                                divide_end = i + 1
                        else:
                            if line[i] not in whitespace:
                                divide_start = i + 1
                                break
                    spaces.append((divide_start, divide_end))
                print spaces
                align_col = 0
                for s in spaces:
                    if s[0] > align_col:
                        align_col = s[0]
                align_col += 1
                print align_col
                for i, ln in zip(range(len(line_nums)), line_nums):
                    pt = view.text_point(ln, spaces[i][0])
                    elength = spaces[i][1] - spaces[i][0]
                    alength = align_col - spaces[i][0]

                    view.erase(edit, sublime.Region(pt, pt + elength))
                    view.insert(edit, pt, ' '*alength)






        if not alignment_chars:
            # nothing to align on
            return



        points  = []
        max_col = 0
        for row in line_nums:
            pt = view.text_point(row, 0)

            # Determine if the line is a variable declaration or just
            #  a variable setting operation

            # Find the first character we are going to align correctly
            matching_region = view.find(alignment_pattern, pt)

            if 0 and settings.get('alignment_align_var_defs') and \
               (not matching_region or \
               view.rowcol(matching_region.a)[0] != row):

                var_define_align = True

                # If we didn't find one of the specified alignment
                #  characters, try to align the last word. This is
                #  useful for variable declarations.
                l = view.line(pt)
                found_word = False
                for i in range(l.b, l.a, -1):
                    char = view.substr(i)
                    if found_word:
                        if char == ' ' or char == '\t':
                            matching_char_pt = i
                            insert_pt = i
                            break
                    else:
                        if char != ' ' and char != '\t' and char != '\n':
                            found_word = True
                if not found_word:
                    continue

            else:
                matching_char_pt = matching_region.a
                insert_pt        = matching_region.a
                var_define_align = False

            # If the equal sign is part of a multi-character
            # operator, bring the first character forward also
            if view.substr(insert_pt-1) in alignment_prefix_chars and \
               var_define_align == False:
                insert_pt -= 1

            space_pt = insert_pt
            while view.substr(space_pt-1) in [' ', '\t']:
                space_pt -= 1
                # Replace tabs with spaces for consistent indenting
                if view.substr(space_pt) == '\t':
                    view.replace(edit, sublime.Region(space_pt,
                        space_pt+1), ' ' * tab_size)
                    matching_char_pt += tab_size - 1
                    insert_pt += tab_size - 1

            if view.substr(matching_char_pt) in alignment_space_chars:
                space_pt += 1

            # If the next equal sign is not on this line, skip the line
            if view.rowcol(matching_char_pt)[0] != row:
                continue

            points.append(insert_pt)
            max_col = max([max_col, normed_rowcol(view, space_pt)[1]])

        # The adjustment takes care of correcting point positions
        # since spaces are being inserted, which changes the points
        adjustment = 0
        for pt in points:
            pt += adjustment
            length = max_col - normed_rowcol(view, pt)[1]
            adjustment += length
            if length >= 0:
                view.insert(edit, pt, ' ' * length)
            else:
                view.erase(edit, sublime.Region(pt + length, pt))

            if settings.get('mid_line_tabs') and not use_spaces:
                adjustment += convert_to_mid_line_tabs(view, edit,
                    tab_size, pt, length)



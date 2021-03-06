import os, sys, re, math, datetime, time
import numpy as np
from operator import itemgetter
from slalom_structures import DefaultOrderedDict, InputData, CurrentSequence, BasicBooleanMeasures, BasicEnrichmentMeasures, PerformanceMeasures, FileHandlers

def error(message):
    """Function for error reporting"""
    sys.stderr.write('Error: {}\n'.format(message))
    sys.stderr.flush()
    sys.exit(1)

class ArgumentValidator:
    """Class that contain means to command line argument validation"""
    prefixes = {'s': 'len_db', 'm': 'group_map', 'a1': 'anno1', 'a2': 'anno2'}
    suffixes = {'d': 'delimiter', 'h': 'headers', 'c': 'columns', 'q': 'quotes'}
    misc_keys = {'-ovs': 'overlap_symbols', '-ovp': 'overlap_part', '-n': 'enrichment_count', '-maxsize': 'max_group_size', '-w': 'warnings', '-l': 'seq_len'}
    def __init__(self, opt):
        self.opt = opt
        self.file_control_regex = '-({})({})'.format('|'.join(self.prefixes), '|'.join(self.suffixes))
    def _get_file_control_option_value(self, key):
        """Method to retrieve values of file control command line options by their keys"""
        regex_search = re.search(self.file_control_regex, key)
        if not regex_search:
            return None
        dest = '{}_{}'.format(self.prefixes[regex_search.group(1)], self.suffixes[regex_search.group(2)])
        return getattr(self.opt, dest)
    def validate_file_paths(self):
        """Method to check for validity of given input and output file paths"""
        if (self.opt.seq_len == 0) and (not self.opt.series_start) and (not os.path.isfile(self.opt.len_db)):
            if not self.opt.len_db:
                error('Neither input file with the database of sequence lengths nor the common sequence length is not provided')
            error('Input file with the database of sequence lengths does not exist')
        if self.opt.group_map:
            if not os.path.isfile(self.opt.group_map):
                error('Input file with the sequence group mapping does not exist')
        if not os.path.isfile(self.opt.anno1):
            error('Input file with the first annotation does not exist')
        if not os.path.isfile(self.opt.anno2):
            error('Input file with the second annotation does not exist')
    def validate_file_column_numbers(self):
        """Method to check for validity the options listing column numbers in the files"""
        for key in ('-sc', '-mc', '-a1c', '-a2c'):
            if key == '-mc':
                if not self.opt.group_map:
                    continue
                n = 2
            elif key == '-sc':
                if not self.opt.len_db:
                    continue
                n = 2 if self.opt.time_unit == 'none' else 3
                if self.opt.single_sequence:
                    n -= 1
            else:
                if self.opt.single_sequence or getattr(self.opt, 'anno' + key[2] + '_all_sequences'):
                    n = 2
                else:
                    n = 3 if ((not self.opt.group_map) or getattr(self.opt, 'anno' + key[2] + '_all_groups')) else 4
                if self.opt.site_names:
                    n += 1
            regex = '^([1-9]\d*,){{{}}}[1-9]\d*$'.format(n - 1)
            if not re.search(regex, self._get_file_control_option_value(key)):
                if n > 1:
                    error("Invalid format for the option '{}'. Expected a list of {} comma-delimited positive integers".format(key, n))
                else:
                    error("Invalid format for the option '{}'. Expected a positive integer".format(key))
    def validate_delimiters(self):
        """Method to check for validity the delimiters for the input files"""
        regex = re.compile('''^[ \t,;.:/]$''')
        for key in ('-sd', '-md', '-a1d', '-a2d'):
            value = self._get_file_control_option_value(key)
            if not regex.match(value):
                error("Invalid value for the option '{}'. Expected a character from the set ' \t,;.:/'".format(key))
    def validate_numerical_options_boundaries(self):
        """Method to check if numerical option values lie in correct boundaries"""
        for key in ('-sh', '-mh', '-a1h', '-a2h'):
            if self._get_file_control_option_value(key) < 0:
                error("Invalid value for the option '{}'. Expected a non-negative integer".format(key))
        for key in ('-l', '-n', '-maxsize'):
            if getattr(self.opt, self.misc_keys[key]) < 0:
                error("Invalid value for the option '{}'. Expected a non-negative integer".format(key))
        for key in ('-ovs', ):
            if getattr(self.opt, self.misc_keys[key]) < 1:
                error("Invalid value for the option '{}'. Expected a positive integer".format(key))
        for key in ('-ovp', ):
            value = getattr(self.opt, self.misc_keys[key])
            if (value < 0.0) or (value > 1.0):
                error("Invalid value for the option '{}'. Expected a value in range [0,1]".format(key))
        for key in ('-w', ):
            value = getattr(self.opt, self.misc_keys[key])
            if (value < 0) or (value > 1):
                error("Invalid value for the option '{}'. Expected an integer in range [0,1]".format(key))
    def validate_logic(self):
        """Method to validate the logic of the interplay of different parameters"""
        present = False
        for i in ('1', '2'):
            if getattr(self.opt, 'output_file_re' + i):
                present = True
        if present and (not getattr(self.opt, 'enrichment_count')):
            error('Relative enrichment output files can be written only in enrichment mode')
        if self.opt.len_db and (self.opt.seq_len > 0):
            error('Positive lengrh of all sequence and the file with the database of sequence lengths cannot be provided simultaneously')
        if self.opt.gross and getattr(self.opt, 'enrichment_count'):
            error('Gross symbol counting is possible only in Boolean mode')
        if (self.opt.anno1_resolve_overlaps or self.opt.anno2_resolve_overlaps) and getattr(self.opt, 'enrichment_count'):
            error('Overlap resolving within a given annotation is possible only in Boolean mode')
        if self.opt.preparse_group_map and (not self.opt.group_map):
            error('To preprse the group mapping it must be provided')
        if self.opt.seq_len and (self.opt.time_unit != 'none'):
            error('Positive length of all sequences is not compatible with time series')
        if (self.opt.series_start or self.opt.series_finish) and (self.opt.time_unit == 'none'):
            error('Start and finish of all sequences can be specified only for time series')
        if bool(self.opt.series_start) != bool(self.opt.series_finish):
            error('Start and finish of all sequences must be provided together')
        if (not self.opt.len_db) and self.opt.group_map and (not self.opt.preparse_group_map):
            if self.opt.warnings:
                print('The sequence length database is not provided. The preparsing of the group mapping is activated automatically')
        if self.opt.single_sequence and self.opt.group_map:
            error('Group mapping is not compatible with the option of processing single sequence')
        if self.opt.anno1_all_sequences and self.opt.anno2_all_sequences:
            error('The option of treating all sites as belonging to all sequences cannot be activated for both annotations')
        if (self.opt.anno1_all_sequences and self.opt.anno1_all_groups) or (self.opt.anno2_all_sequences and self.opt.anno2_all_groups):
            error('The options of treating all sites as belonging to all sequences and all groups are not compatible for the same annotation')
        if (not self.opt.len_db) and (not self.opt.group_map) and (self.opt.anno1_all_sequences or self.opt.anno2_all_sequences):
            error('For the options of treating all sites as belonging to all sequences either the length database or the group mapping is required')
        if (self.opt.anno1_all_groups or self.opt.anno2_all_groups) and (not self.opt.group_map):
            error('The options of treating all sites as belonging to all groups can be activated only if the group mapping is provided')
        if (not self.opt.benchmark) and (self.opt.predictor_nature != 'neutral'):
            error('The predictor nature can be only neutral if neither annotation is set as benchmark')
        if ((self.opt.anno1_resolve_overlaps == 'merge') or (self.opt.anno2_resolve_overlaps == 'merge')) and self.opt.site_names:
            error('Named sites are not compatible with merging while resolving overlaps')
        if (self.opt.overlap_apply == 'patched') and (self.opt.site_difference == 'discrepant'):
            error('Showing only discreoant in the site-wise output is not compatible with the patched overlap logic')

class ArgumentProcessor:
    """Class to coordinate command line argument parsing"""
    def __init__(self, arg_parser):
        self.arg_parser = arg_parser
    def _check_if_empty(self):
        """Method to check if the argument list is empty"""
        if len(sys.argv) == 1:
            self.arg_parser.print_help()
            sys.exit()
    def prepare_input_options(self):
        """Method to genarae validated object with the command line options"""
        self._check_if_empty()
        opt = self.arg_parser.parse_args()
        validator = ArgumentValidator(opt)
        validator.validate_file_paths()
        validator.validate_file_column_numbers()
        validator.validate_delimiters()
        validator.validate_numerical_options_boundaries()
        validator.validate_logic()
        return opt
        
class CSVParser:
    """Class to parse the input CSV files"""
    field_regex_quoted = '''((?:[^{0}"']|"[^"]*(?:"|$)|'[^']*(?:'|$))+|(?={0}{0})|(?={0}$)|(?=^{0}))'''
    field_regex_simple = '(?:[^{0}]+|(?={0}{0})|(?={0}$)|(?=^{0}))'
    quote_compiled = re.compile('''['"]''')
    int_regex = re.compile('^[+-]?\d*$')
    pos_int_regex = re.compile('^\+?[1-9]\d*$')
    time_formats_compiled = [re.compile(x) for x in ('^\d\d/\d\d/\d{4} \d\d:\d\d:\d\d$', '^\d\d/\d\d/\d{4} \d\d:\d\d$', '^\d\d\.\d\d\.\d{4} \d\d:\d\d:\d\d$', '^\d\d\.\d\d\.\d{4} \d\d:\d\d$')]
    time_formats = ['%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%d.%m.%Y %H:%M:%S', '%d.%m.%Y %H:%M']
    def __init__(self, opt, global_state):
        self.opt = opt
        self.global_state = global_state
        self.input_data = InputData()
    def _parse_input_file(self, opt_prefix, preliminary = False):
        """Method to parse an input file"""
        column_indices = tuple(int(x) - 1 for x in getattr(self.opt, opt_prefix + '_columns').split(','))
        filename = getattr(self.opt, opt_prefix)
        delimiter = getattr(self.opt, opt_prefix + '_delimiter')
        quotes_as_escaped = getattr(self.opt, opt_prefix + '_quotes')
        file_field = re.compile(getattr(CSVParser, 'field_regex_simple' if quotes_as_escaped else 'field_regex_quoted').format(delimiter))
        with open(filename, 'r') as ifile:
            for i in range(getattr(self.opt, opt_prefix + '_headers')):
                next(ifile)
            for line_idx, line in enumerate(ifile):
                try:
                    values = itemgetter(*column_indices)(file_field.findall(line.strip('\n')))
                except IndexError:
                    print('~{}~{}~{}~'.format(column_indices, line, quotes_as_escaped))##/
                    error('Error while parsing the line {} of the file "{}". Not enough columns delimited by "{}" identified'.format(line_idx + 1, filename, delimiter))
                if not quotes_as_escaped:
                    values = [CSVParser.quote_compiled.sub('', el) for el in values]
                try:
                    self._save_record(opt_prefix, values, preliminary)
                except RuntimeError as e:
                    error('Error while parsing the line {} of the file "{}". {}'.format(line_idx + 1, filename, str(e)))
    def _duration_in_units(self, start_time_point, finish_time_point):
        """Method to calculate the distance in time, measured in speciied by the user units, between two points"""
        return math.floor((time.mktime(finish_time_point) - time.mktime(start_time_point)) / self.global_state.time_unit_seconds)
    def _convert_interval_to_time_structs(self, interval):
        """Mathod to convert time strings in an interval to time_struct objects"""
        for interval_idx, time_str in enumerate(interval):
            recognized = False
            for time_format_idx, time_format_compiled in enumerate(CSVParser.time_formats_compiled):
                if time_format_compiled.search(time_str):
                    recognized = True
                    try:
                        interval[interval_idx] = time.strptime(time_str, CSVParser.time_formats[time_format_idx])
                    except ValueError:
                        raise RuntimeError('Time format was not recognized. Supported formats: "mm/dd/yyyy HH:MM[:SS]" and "dd.mm.yyyy HH:MM[:SS]"') from None
                    break
            if not recognized:
                raise RuntimeError('Time format was not recognized. Supported formats: "mm/dd/yyyy HH:MM[:SS]" and "dd.mm.yyyy HH:MM[:SS]"')
    def _save_seq_len_db_record(self, values, not_first_to_check):
        """Method to save a sequence length database record"""
        def _save_record():
            """Closure to write the values to the corresponding dictionaries"""
            nonlocal seq_length
            self.input_data.seq_len[SID] = seq_length
            if self.global_state.time_unit_seconds:
                nonlocal interval
                self.input_data.time_series_starts[SID] = interval[0]
        if not self.global_state.time_unit_seconds:
            if self.opt.single_sequence:
                seq_length = values[0]
                SID = ''
            else:
                SID, seq_length = values
            if not self.pos_int_regex.search(seq_length):
                raise RuntimeError('Sequence length must be a positive integer')
        else:
            if self.opt.single_sequence:
                start, finish = values
                SID = ''
            else:
                SID, start, finish = values
            interval = [start, finish]
            self._convert_interval_to_time_structs(interval)
            seq_length = self._duration_in_units(interval[0], interval[1])
            if seq_length < 1:
                raise RuntimeError('The time interval must contain at least 1 time unit')
        seq_length = int(seq_length)
        if not_first_to_check:
            if SID not in self.input_data.seq_len.keys():
                return
            if self.input_data.seq_len[SID] is None:
                _save_record()
        else:
            _save_record()
        if (self.opt.single_sequence) and (not SID):
            raise RuntimeError('An SID cannot be empty')
        if '"' in SID:
            raise RuntimeError('An SID cannot contain double quotes')
        if self.input_data.seq_len[SID] != seq_length:
            raise RuntimeError('Inconsistency in the sequence length database. Different length/duration values for a duplicating SID.')
        if self.global_state.time_unit_seconds and (self.input_data.time_series_starts[SID] != interval[0]):
            raise RuntimeError('Inconsistency in the sequence length database. Different start values for a duplicating SID.')
    def _save_group_map_record(self, values, preliminary = False):
        """Method to save a group mapping record"""
        SID, GID = values
        if not GID:
            raise RuntimeError('A GID cannot be empty')
        if '"' in GID:
            raise RuntimeError('A GID cannot contain double quotes')
        if preliminary:
            self.input_data.seq_len[SID] = self.auto_seq_len
            if self.global_state.time_unit_seconds:
                self.input_data.time_series_starts[SID] = self.auto_series_start
        elif SID not in self.input_data.seq_len.keys():
            if self.opt.warnings:
                print('Warning: SID "{}" is not the sequence length database. The group mapping record is ignored'.format(SID))
            return
        if SID not in self.input_data.group_map[GID]:
            self.input_data.group_map[GID].append(SID)
    def _save_annotation_record(self, opt_prefix, values):
        """Method to save an annotation record"""
        if self.opt.site_names:
            site_name = values[-1]
            if not site_name:
                raise RuntimeError('A site name cannot be empty')
            if '"' in site_name:
                raise RuntimeError('A site name cannot contain double quotes')
            values = values[: -1]
        if self.opt.single_sequence or getattr(self.opt, opt_prefix + '_all_sequences'):
            begin, end = values
            GID = ''
            SID = ''
        elif self.opt.group_map and (not getattr(self.opt, opt_prefix + '_all_groups')):
            begin, end, SID, GID = values
        else:
            begin, end, SID = values
            GID = ''
        GID_list = [GID] if GID else list(self.input_data.group_map.keys())
        for GID_ in GID_list:
            SID_list = [SID] if SID else self.input_data.group_map[GID_]
            for SID_ in SID_list:
                if SID_ not in self.input_data.seq_len.keys():
                    if (not self.opt.len_db) and (not self.opt.group_map):
                        self.input_data.group_map[GID_].append(SID_)
                        self.input_data.seq_len[SID_] = self.auto_seq_len
                        if self.global_state.time_unit_seconds:
                            self.input_data.time_series_starts[SID_] = self.auto_series_start
                    elif self.opt.warnings:
                        print('Warning: SID "{}" is not in the sequence length database. The annotation record is ignored'.format(SID_))
                        return
                if GID_ not in self.input_data.group_map.keys():
                    if self.opt.warnings:
                        print('Warning: GID "{}" is not in the group mapping. The annotation record is ignored'.format(GID_))
                    return
                if SID_ not in self.input_data.group_map[GID_]:
                    if getattr(self.opt, opt_prefix + '_all_groups'):
                        continue
                    raise RuntimeError('SID "{}" does not belong to the group "{}" in the group mapping'.format(SID_, GID_))
                if not self.global_state.time_unit_seconds:
                    if (not self.int_regex.search(begin)) and (not self.int_regex.search(end)):
                        raise RuntimeError('Site begin and end position must be integers')
                    begin_ = int(begin)
                    end_ = int(end)
                else:
                    interval = [begin, end]
                    self._convert_interval_to_time_structs(interval)
                    begin_ = self._duration_in_units(self.input_data.time_series_starts[SID_], interval[0]) + 1
                    end_ = self._duration_in_units(self.input_data.time_series_starts[SID_], interval[1])
                begin_ += getattr(self.opt, opt_prefix + '_begin_shift')
                end_ += getattr(self.opt, opt_prefix + '_end_shift')
                if begin_ < 1:
                    if self.opt.end_overflow_policy == 'error':
                        raise RuntimeError('Site begin position must be positive')
                    elif self.opt.end_overflow_policy == 'trim':
                        if end_ < 1:
                            return
                        begin_ = 1
                    elif self.opt.end_overflow_policy == 'ignore':
                        return
                if begin_ > end_:
                    raise RuntimeError('Site begin position cannot exceed the end position')
                if end_ > self.input_data.seq_len[SID_]:
                    if self.opt.end_overflow_policy == 'error':
                        raise RuntimeError('Site end position cannot exceed the sequence length')
                    elif self.opt.end_overflow_policy == 'trim':
                        end_ = self.input_data.seq_len[SID_]
                        if begin_ > end_:
                            return
                    elif self.opt.end_overflow_policy == 'ignore':
                        return
                no = int(opt_prefix[-1])
                self.input_data.sites[no][GID_][SID_].append([begin_, end_])
                if self.opt.site_names:
                    self.input_data.sites[no][GID_][SID_][-1].append(site_name)
    def _save_record(self, opt_prefix, values, preliminary = False):
        """Method to save a record from an input file"""
        if opt_prefix == 'len_db':
            self._save_seq_len_db_record(values, self.opt.preparse_group_map)
        elif opt_prefix == 'group_map':
            self._save_group_map_record(values, preliminary)
        elif opt_prefix in ('anno1', 'anno2'):   
            self._save_annotation_record(opt_prefix, values)
    def _sort_annotations(self):
        """Method to sort the annotated sites for every sequence by begin symbol number"""
        for i in (1, 2):
            for group in self.input_data.sites[i].values():
                for sites in group.values():
                    sites.sort(key = lambda x: x[0])
    def _resolve_overlaps_within_annotations(self):
        """Method to resolve groups of overlapping sites within a given annotation according to the user-defined policy"""
        for i in (1, 2):
            policy = getattr(self.opt, 'anno{}_resolve_overlaps'.format(i))
            if policy == 'all':
                continue
            for group in self.input_data.sites[i].values():
                for sites in group.values():
                    sites_new = []
                    if policy == 'first':
                        last_end = 0
                        for site in sites:
                            if site[0] > last_end:
                                sites_new.append(site)
                            last_end = site[1]
                    elif policy == 'last':
                        next_begin = float('inf')
                        for site in reversed(sites):
                            if site[1] < next_begin:
                                sites_new.insert(0, site)
                            next_begin = site[0]
                    elif policy == 'merge':
                        last_end = 0
                        new_begin = 0
                        for site in sites:
                            if site[0] > last_end:
                                if new_begin > 0:
                                    sites_new.append([new_begin, last_end])
                                new_begin = site[0]
                            last_end = site[1]
                        if new_begin > 0:
                            sites_new.append([new_begin, last_end])
                    sites[: ] = sites_new       
    def calc_and_set_auto_seq_len(self):
        """Method to calculate the sequence length and, if applicable, the start of time series, on the basis of the input parameters  if the database is not provided"""
        if self.opt.len_db:
            self.auto_seq_len = None
        else:
            if not self.global_state.time_unit_seconds:
                self.auto_seq_len = self.opt.seq_len
            else:
                interval = [self.opt.series_start, self.opt.series_finish]
                try:
                    self._convert_interval_to_time_structs(interval)
                except RuntimeError as e:
                    raise RuntimeError('Time series start and end: ' + e.args[0]) from None
                self.auto_seq_len = self._duration_in_units(interval[0], interval[1])
                self.auto_series_start = interval[0]
    def parse_sequence_length_db(self):
        """Method to parse the input sequence length database file"""
        self._parse_input_file('len_db')
        if self.opt.preparse_group_map:
            for SID in list(self.input_data.seq_len.keys()):
                if self.input_data.seq_len[SID] is None:
                    del self.input_data.seq_len[SID]
                    if self.opt.warnings:
                        print('Warning: SID "{}" is not the sequence length database. The group mapping record is ignored'.format(SID))
            self.input_data.group_map = DefaultOrderedDict(list)
        if not self.input_data.seq_len:
            error('The sequence length database does not contain any SIDs that can be retained')
        print('The sequence length database has been read from "{}"'.format(getattr(self.opt, 'len_db')))
    def parse_group_map(self, preliminary = False):
        """Method to parse the input group map file"""
        if (not preliminary) and (not self.input_data.seq_len):
            error('The sequence length database must be parsed before the group mapping')
        if not self.opt.group_map:
            self.input_data.group_map[''].extend(self.input_data.seq_len.keys())
            return
        self._parse_input_file('group_map', preliminary)
        if (self.opt.min_group_size > 1) or (self.opt.max_group_size > 0):
            for GID in list(self.input_data.group_map.keys()):
                SID_list = self.input_data.group_map[GID]
                if (len(SID_list) < self.opt.min_group_size) or (self.opt.max_group_size and (len(SID_list) > self.opt.max_group_size)):
                    del self.input_data.group_map[GID]
        if not self.input_data.group_map:
            error('The sequence length database does not contain any SIDs that can be retained')
        print('The group mapping has been{} read from "{}"'.format(' preliminary' if self.auto_seq_len is None else '', getattr(self.opt, 'group_map')))
    def parse_annotations(self):
        """Method to parse the input annotation files"""
        if (self.opt.len_db and (not self.input_data.seq_len)) or (not self.input_data.group_map):
            error('The annotation files must be parsed after the sequence length database and the group mapping')
        self._parse_input_file('anno1')
        print('The first annotation has been read from "{}"'.format(getattr(self.opt, 'anno1')))
        self._parse_input_file('anno2')
        print('The second annotation has been read from "{}"'.format(getattr(self.opt, 'anno2')))
        if (not self.input_data.sites[1]) or (not self.input_data.sites[2]):
            error('An annotation must not be empty')
        self._sort_annotations()
        self._resolve_overlaps_within_annotations()
    def get_data(self):
        return self.input_data

class InputFileProcessor:
    """Class for coordinating the input file processing"""
    def __init__(self, opt, file_parser):
        self.opt = opt
        self.file_parser = file_parser
    def process_input_files(self):
        """Method to coordinate processing of the input files"""
        self.file_parser.calc_and_set_auto_seq_len()
        if self.opt.preparse_group_map or (not self.opt.len_db):
            self.file_parser.parse_group_map(preliminary = True)
        if self.opt.len_db:
            self.file_parser.parse_sequence_length_db()
            self.file_parser.parse_group_map()
        self.file_parser.parse_annotations()
        return self.file_parser.get_data()

class BasicSequenceCalculator:
    """Abstract class for calculating basic measures and write into files required output annotations in a paricular sequence"""
    def __init__(self, global_state, opt, current_seq):
        self.global_state = global_state
        self.opt = opt
        self.current_seq = current_seq
        self.results = None
    def _in_union(self, idx):
        """Method to check if given symbol is in the annotation union"""
        raise NotImplementedError("Method '_in_union' is not implemented")
    def _in_intersection(self, idx):
        """Method to check if given symbol is in the annotation intersection"""
        raise NotImplementedError("Method '_in_intersection' is not implemented")
    def _in_complement1(self, idx):
        """Method to check if given symbol is in the annotation complement of the first"""
        raise NotImplementedError("Method '_in_complement1' is not implemented")
    def _in_complement2(self, idx):
        """Method to check if given symbol is in the annotation complement of the second"""
        raise NotImplementedError("Method '_in_complement2' is not implemented")
    def _in_re1(self, idx):
        """Method to check if given symbol is in the annotation of relative enrichment for the first annotation"""
        raise NotImplementedError("Method '_in_re1' is not implemented")
    def _in_re2(self, idx):
        """Method to check if given symbol is in the annotation of relative enrichment for the first annotation"""
        raise NotImplementedError("Method '_in_re2' is not implemented")
    def _write_site(self, file_handler, begin_idx, idx):
        """Auxiliary method to write a site to an output annotation file"""
        group = (self.current_seq.GID + '\t' if self.current_seq.GID else '')
        file_handler.write('{}{}\t{}\t{}\n'.format(group, self.current_seq.SID, begin_idx + 1, idx))
    def write_to_files(self, file_handlers):
        """Method to write the required output annotations"""
        for type_ in FileHandlers.output_file_types:
            file_handler = getattr(file_handlers, type_)
            if file_handler is None:
                continue
            if type_ in ('detailed', 'site'):
                continue
            else:
                in_site = False
                begin_idx = None
                for idx in range(self.current_seq.length):
                    if getattr(self, '_in_' + type_)(idx):
                        if not in_site:
                            in_site = True
                            begin_idx = idx
                    elif in_site:
                        self._write_site(file_handler, begin_idx, idx)
                        in_site = False
                if in_site:
                    self._write_site(file_handler, begin_idx, self.current_seq.length)
    def calculate_residue_wise(self):
        """Method to calculate residue-wise measures for a given sequence"""
        raise NotImplementedError("Method 'calculate_residue_wise' is not implemented")
    def get_results(self):
        return self.results

class BasicBooleanSequenceCalculator(BasicSequenceCalculator):
    """Class for calculating basic Boolean measures and write into files required output annotations in a particular sequence"""
    def __init__(self, global_state, opt, current_seq):
        BasicSequenceCalculator.__init__(self, global_state, opt, current_seq)
        self.seq = np.zeros(shape = current_seq.length, dtype = 'i1')
        self.results = BasicBooleanMeasures()
        self._classify_symbols()
    def _classify_symbols(self):
        """Method to classify symbols in the sequence by their occurrence in the annotations"""
        for site in self.current_seq.sites[1]:
            for idx in range(site[0] - 1, site[1]):
                self.seq[idx] = 1
        for site in self.current_seq.sites[2]:
            for idx in range(site[0] - 1, site[1]):
                if self.seq[idx] == 0:
                    self.seq[idx] = 2
                elif self.seq[idx] == 1:
                    self.seq[idx] = 3
    def _in_union(self, idx):
        """Method to check if given symbol is in the Bollean annotation union"""
        return True if self.seq[idx] >= 1 else False
    def _in_intersection(self, idx):
        """Method to check if given symbol is in the Bollean annotation intersection"""
        return True if self.seq[idx] == 3 else False
    def _in_complement1(self, idx):
        """Method to check if given symbol is in the Bollean annotation complement of the first"""
        return True if self.seq[idx] == 2 else False
    def _in_complement2(self, idx):
        """Method to check if given symbol is in the Bollean annotation complement of the second"""
        return True if self.seq[idx] == 1 else False
    def _get_overlapped_symbols(self, site, site_, annotation_idx):
        """Method to calculate number of shared symbols between two sites in the same sequence"""
        if self.opt.predictor_nature != 'neutral':
            if (self.opt.predictor_nature == 'lagging') == (annotation_idx == 1):
                if site_[0] < site[0]:
                    return 0
            elif site_[0] > site[0]:
                return 0
        return max(min(site[1] - site_[0], site_[1] - site[0], site[1] - site[0], site_[1] - site_[0]) + 1, 0)
    def _get_site_length(self, site, site_):
        """Method to calculate the effective site length according to the input settings"""
        if self.opt.overlap_apply == 'shortest':
            return min(site[1] - site[0], site_[1] - site_[0]) + 1
        elif self.opt.overlap_apply == 'longest':
            return max(site[1] - site[0], site_[1] - site_[0]) + 1
        elif self.opt.overlap_apply in ('current', 'patched'):
            return site[1] - site[0] + 1
    def _check_overlap_sufficiency(self, overlapped_symbols, site_length):
        """Method to check if a goven overlap between sites satisfies the input overlap criteria"""
        return (overlapped_symbols >= self.opt.overlap_symbols) and (overlapped_symbols / site_length >= self.opt.overlap_part)
    def _write_measure_info_to_detailed_file(self, type_, description, detailed_file_h):
        """Writing the information on sybol counts in a specific category"""
        symbols_n = getattr(self.results, type_)
        category_name = getattr(self.global_state, type_ + '_name')
        ending = '{} is' if symbols_n == 1 else 's{} are'
        ending = ending.format(' gross' if (self.opt.gross and (type_ != 'aa')) else '')
        detailed_file_h.write('{}{} symbol{} {}{}'.format(self.global_state.indent_site, symbols_n, ending, description, category_name) + os.linesep)
    def calculate_residue_wise(self, detailed_file_h):
        """Method to calculate Boolean residue-wise measures for a given sequence and write the information to the detailed output file"""
        if self.opt.gross:
            self.results.pa = 0
            self.results.ap = 0
            for i in (1, 2):
                j = 3 - i
                for site in self.current_seq.sites[i]:
                    matched_symbols_n = np.sum(self.seq[site[0] - 1: site[1]] == 3)
                    site_length = site[1] - site[0] + 1
                    unmatched_symbols_n = site_length - matched_symbols_n
                    self.results.pp_[i] += matched_symbols_n
                    attr_name = 'pa' if i == 1 else 'ap'
                    setattr(self.results, attr_name, getattr(self.results, attr_name) + unmatched_symbols_n)
                if detailed_file_h:
                    ending = ('' if self.results.pp_[i] == 1 else 's') + ' gross'
                    message = '{}{} symbol{} present in the {} are also present in the {}'
                    detailed_file_h.write(message.format(self.global_state.indent_site, self.results.pp_[i], ending, self.global_state.anno_name[i], self.global_state.anno_name[j]) + os.linesep)
        else:
            self.results.pp = np.sum(self.seq == 3)
            self.results.pp_[1] = self.results.pp
            self.results.pp_[2] = self.results.pp
            if detailed_file_h:
                self._write_measure_info_to_detailed_file('pp', 'present in both annotations', detailed_file_h)
            self.results.pa = np.sum(self.seq == 1)
            self.results.ap = np.sum(self.seq == 2)
        self.results.aa = np.sum(self.seq == 0)
        if detailed_file_h:
            description = 'present exclusively in the ' + self.global_state.anno_name[1]
            self._write_measure_info_to_detailed_file('pa', description, detailed_file_h)
            description = 'present exclusively in the ' + self.global_state.anno_name[2]
            self._write_measure_info_to_detailed_file('ap', description, detailed_file_h)
            self._write_measure_info_to_detailed_file('aa', 'absent in both annotations', detailed_file_h)
    def calculate_site_wise(self, detailed_file_h, site_file_h):
        """Method to calculate site-wise measures and write the site-wise information to the detailed output file"""
        if self.opt.overlap_apply in ('shortest', 'longest', 'current'):
            for i in (1, 2):
                j = 3 - i
                last_end = 0
                for site in self.current_seq.sites[i]:
                    site_effective_begin = site[0] if self.opt.gross else max(site[0], last_end + 1)
                    self.results.site_len[i] += site[1] - site_effective_begin + 1
                    last_end = site[1]
                    found_match = False
                    for site_ in self.current_seq.sites[j]:
                        if site_[0] > site[1]:
                            break
                        overlapped_symbols = self._get_overlapped_symbols(site, site_, i)
                        site_length_effective = self._get_site_length(site, site_)
                        if self._check_overlap_sufficiency(overlapped_symbols, site_length_effective):
                            self.results.site_m[i] += 1
                            found_match = True
                            break
                    if not found_match:
                        self.results.site_nm[i] += 1
                    if (detailed_file_h is not None) or (site_file_h is not None):
                        if found_match:
                            length_perc_1 = round(100 * overlapped_symbols / (site[1] - site[0] + 1))
                            length_perc_2 = round(100 * overlapped_symbols / (site_[1] - site_[0] + 1))
                            begin_ = site_[0]
                            end_ = site_[1]
                        else:
                            overlapped_symbols = length_perc_1 = length_perc_2 = 0
                            begin_ = end_ = '-'
                        if detailed_file_h is not None:
                            site_name_addition = ' ("{}")'.format(site[2]) if self.opt.site_names else ''
                            message = '{}Site {}-{}{} of the {}: '.format(self.global_state.indent_site, site[0], site[1], site_name_addition, self.global_state.anno_name[i])
                            if found_match:
                                ending = '' if overlapped_symbols == 1 else 's'
                                site_name_addition_ = ' ("{}")'.format(site_[2]) if self.opt.site_names else ''
                                message += 'overlaps with site {}-{}{} of the {} by {} symbol{} ({}% and {}% of the site lengths respectively)'
                                message = message.format(site_[0], site_[1], site_name_addition_, self.global_state.anno_name[j], overlapped_symbols, ending, length_perc_1, length_perc_2)
                            else:
                                message += 'no sufficient overlap found'
                            detailed_file_h.write(message + os.linesep)
                        if site_file_h is not None:
                            if self.opt.site_difference == 'unmatched':
                                if found_match:
                                    continue
                            elif self.opt.site_difference == 'discrepant':
                                if (length_perc_1 == 100) and (length_perc_2 == 100):
                                    continue
                            list_ = [self.current_seq.GID] if self.opt.group_map else []
                            list_.extend([self.current_seq.SID, self.global_state.anno_short_name[i], site[0], site[1]])
                            if self.opt.site_names:
                                list_.append(site[2])
                            list_.extend([overlapped_symbols, length_perc_1, length_perc_2, begin_, end_])
                            if self.opt.site_names:
                                list_.append(site_[2] if found_match else '')
                            message = ('{}\t' * (len(list_) - 1) + '{}').format(*list_)
                            site_file_h.write(message + os.linesep)
        elif self.opt.overlap_apply == 'patched':
            for i in (1, 2):
                for site in self.current_seq.sites[i]:
                    matched_symbols = np.sum(self.seq[site[0] - 1: site[1]] == 3)
                    site_length = site[1] - site[0] + 1
                    found_match = self._check_overlap_sufficiency(matched_symbols, site_length)
                    if found_match:
                        self.results.site_m[i] += 1
                    else:
                        self.results.site_nm[i] += 1
                    if (detailed_file_h is not None) or (site_file_h is not None):
                        if found_match:
                            length_perc = round(100 * matched_symbols / site_length)
                        else:
                            length_perc = 0
                        if detailed_file_h is not None:
                            message = '{}Site {}-{} of the {}: '.format(self.global_state.indent_site, site[0], site[1], self.global_state.anno_name[i])
                            if found_match:
                                ending = '' if matched_symbols == 1 else 's'
                                message += 'overlaps by total {} symbol{} ({}% of the site length) with sites from the {}'.format(matched_symbols, ending, length_perc, self.global_state.anno_name[j])
                            else:
                                message += 'no sufficient overlap found'
                            detailed_file_h.write(message + os.linesep)
                    if site_file_h is not None:
                        if found_match and (self.opt.site_difference == 'unmatched'):
                            continue
                        list_ = [self.current_seq.GID] if self.opt.group_map else []
                        list_.extend([self.current_seq.SID, self.global_state.anno_short_name[i], site[0], site[1]])
                        if self.opt.site_names:
                            list_.append(site[2])
                        list_.extend([overlapped_symbols, length_perc])
                        message = ('{}\t' * (len(list_) - 1) + '{}').format(*list_)
                        site_file_h.write(message + os.linesep)
        else:
            error('Unknown overlap apply method')
        for i in (1, 2):
            sites_n = self.results.site_m[i] + self.results.site_nm[i]
            if sites_n == 0:
                if detailed_file_h:
                    detailed_file_h.write('{}There are no sites in the {}'.format(self.global_state.indent_site, self.global_state.anno_name[i]) + os.linesep)
                continue
            else:
                ending = '' if sites_n == 1 else 's'
                verb = 'is' if sites_n == 1 else 'are'
                symbols = self.results.site_len[i]
                ending1 = '' if symbols == 1 else 's'
                insert0 = '' if self.opt.gross else ' unique'
                insert1 = ' gross' if self.opt.gross else ''
                message_base = '{}There {} {} site{} in the {} with total length {}{} symbol{}{}'
                if detailed_file_h:
                    detailed_file_h.write(message_base.format(self.global_state.indent_site, verb, sites_n, ending, self.global_state.anno_name[i], symbols, insert0, ending1, insert1) + os.linesep)
            if detailed_file_h:
                sites_n = self.results.site_m[i]
                ending = ' is' if sites_n == 1 else 's are'
                detailed_file_h.write('{}{} {} site{} matched in the {}'.format(self.global_state.indent_site, sites_n, self.global_state.anno_name[i], ending, self.global_state.anno_name[j]) + os.linesep)
                sites_n = self.results.site_nm[i]
                ending = ' has' if sites_n == 1 else 's have'
                detailed_file_h.write('{}{} {} site{} no match in the {}'.format(self.global_state.indent_site, sites_n, self.global_state.anno_name[i], ending, self.global_state.anno_name[j]) + os.linesep)
        
class BasicEnrichmentSequenceCalculator(BasicSequenceCalculator):
    """Class for calculating basic enrichment measures and write into files required output annotations in a particular sequence"""
    def __init__(self, global_state, opt, current_seq):
        BasicSequenceCalculator.__init__(self, global_state, opt, current_seq)
        self.n = self.opt.enrichment_count
        bytes_required = self._estimate_required_precison()
        self.seq = [None] + [np.zeros(shape = current_seq.length, dtype = 'i' + str(bytes_required)) for x in range(2)]
        self.results = BasicEnrichmentMeasures()
        self._count_occurrences()
    def _count_occurrences(self):
        """Method to count the occurences in the annotations for each symbol in the sequence"""
        for i in (1, 2):
            for site in self.current_seq.sites[i]:
                for idx in range(site[0] - 1, site[1]):
                    self.seq[i][idx] += 1
    def _in_union(self, idx):
        """Method to check if given symbol is in the enrichment annotation union"""
        for i in (1, 2):
            if self.seq[i][idx] >= self.n:
                return True
        return False
    def _in_intersection(self, idx):
        """Method to check if given symbol is in the enrichment annotation intersection"""
        check = 0
        for i in (1, 2):
            if self.seq[i][idx] >= self.n:
                check += 1
        return True if check == 2 else False
    def _in_complement1(self, idx):
        """Method to check if given symbol is in the enrichment annotation complement of the first"""
        return True if (self.seq[1][idx] < self.n) and (self.seq[2][idx] >= self.n) else False
    def _in_complement2(self, idx):
        """Method to check if given symbol is in the enrichment annotation complement of the second"""
        return True if (self.seq[1][idx] >= self.n) and (self.seq[2][idx] < self.n) else False
    def _in_re1(self, idx):
        """Method to check if given symbol is in the annotation of relative enrichment for the first annotation"""
        return True if self.seq[1][idx] - self.seq[2][idx] >= self.n else False
    def _in_re2(self, idx):
        """Method to check if given symbol is in the annotation of relative enrichment for the first annotation"""
        return True if self.seq[2][idx] - self.seq[1][idx] >= self.n else False
    def _estimate_required_precison(self):
        """Method to provide a higher estimation for the reeqired integer precision of the counts"""
        count_limit = max(len(self.current_seq.sites[1]), len(self.current_seq.sites[2])) + 1
        bytes_required = math.ceil((math.ceil(math.log(count_limit, 2)) + 1) / 8)
        if bytes_required > 8:
            error("Too  many sites annotated. Maximal number is {}".format(2 ** 63 - 1))
        bytes_required = [1, 1, 2, 4, 4, 8, 8, 8, 8][bytes_required]
        return bytes_required
    def _write_measure_info_to_detailed_file(self, symbols_n, description, file_handler):
        """Writing the information on sybol counts in a specific category"""
        ending = ' is' if symbols_n == 1 else 's are'
        file_handler.write('{}{} symbol{} enriched in {}'.format(self.global_state.indent_site, symbols_n, ending, description) + os.linesep)
    def calculate_residue_wise(self, file_handler):
        """Method to calculate count residue-wise measures for a given sequence"""
        for i in (1, 2):
            j = 2 if i == 1 else 1
            self.results.e[i] = np.sum(self.seq[i] >= self.n)
            description = 'the ' + self.global_state.anno_name[i]
            self._write_measure_info_to_detailed_file(self.results.e[i], description, file_handler)
            self.results.re[i] = np.sum((self.seq[i] - self.seq[j]) >= self.n)
        self.results.ee = np.sum((self.seq[1] >= self.n) * (self.seq[2] >= self.n))
        self._write_measure_info_to_detailed_file(self.results.ee, 'both annotations', file_handler)
        self.results.ne = np.sum((self.seq[1] < self.n) * (self.seq[2] < self.n))
        self._write_measure_info_to_detailed_file(self.results.ne, 'neither annotations', file_handler)
        self.results.nre = self.seq_length - self.results.re[1] - self.results.re[2]

class BasicCalculator:
    """Class to calculate selected basic measures and write into files required output annotations for a sequence group"""
    def __init__(self, global_state, opt, input_data, file_handlers):
        self.global_state = global_state
        self.opt = opt
        self.input_data = input_data
        self.file_handlers = file_handlers
    def _process_sequence(self, current_seq):
        """Method to calculate basic measures for annotatopns of sites in a particular sequence in a particular group"""
        args = (self.global_state, self.opt, current_seq)
        if self.file_handlers.detailed is not None:
            ending = '' if current_seq.length == 1 else 's'
            self.file_handlers.detailed.write('{}Information on the sequence "{}" (length {} symbol{}):'.format(self.global_state.indent_seq, current_seq.SID, current_seq.length, ending) + os.linesep)
        basic_sequence_calculator = BasicBooleanSequenceCalculator(*args) if self.opt.enrichment_count == 0 else BasicEnrichmentSequenceCalculator(*args)
        basic_sequence_calculator.calculate_residue_wise(self.file_handlers.detailed)
        if self.opt.enrichment_count == 0:
            basic_sequence_calculator.calculate_site_wise(self.file_handlers.detailed, self.file_handlers.site)
        basic_sequence_calculator.write_to_files(self.file_handlers)
        return basic_sequence_calculator.get_results()
    def process_group(self, GID):
        """Method to calculate basic measures for a giben sequence group"""
        group_results = None
        averaging_count = 0
        if self.opt.group_map and (self.file_handlers.detailed is not None):
            group_len = len(self.input_data.group_map[GID])
            self.file_handlers.detailed.write('Information on the group "{}" (contains {} sequence{}):'.format(GID, group_len, ('s' if group_len > 1 else '')) + os.linesep)
        for SID in self.input_data.group_map[GID]:
            seq_length = self.input_data.seq_len[SID]
            sites = [None] + [self.input_data.sites[i][GID][SID] for i in (1, 2)]
            current_seq = CurrentSequence(GID, SID, seq_length, sites)
            results = self._process_sequence(current_seq)
            if not self.opt.groupwise:
                results /= seq_length
            averaging_count += (seq_length if self.opt.groupwise else 1)
            if group_results is None:
                group_results = results
                continue
            group_results += results
        group_results /= averaging_count
        group_results.seq_n = len(self.input_data.group_map[GID])
        return group_results
        
class PerformanceCalculator:
    """Class to calculate all selected performance measures and write into files required output annotations for a given group"""
    def __init__(self, global_state, opt, input_data, file_handlers):
        self.global_state = global_state
        self.opt = opt
        self.input_data = input_data
        self.file_handlers = file_handlers
    def _calc_p1(self):
        """Method to calculate share of symbols present in the first annotation"""
        p1 = self.basic_measures.pp + self.basic_measures.pa
        self.performance_measures.set_value('p1', p1)
    def _calc_p2(self):
        """Method to calculate share of symbols present in the second annotation"""
        p2 = self.basic_measures.pp + self.basic_measures.ap
        self.performance_measures.set_value('p2', p2)
    def _calc_pp(self):
        """Method to copy share of symbols present in both annotations"""
        pp = self.basic_measures.pp
        self.performance_measures.set_value('pp', pp)
    def _calc_pp1(self):
        """Method to copy share of symbols gross present in the first annotation that are also present in the second"""
        pp1 = self.basic_measures.pp_[1]
        self.performance_measures.set_value('pp1', pp1)
    def _calc_pp2(self):
        """Method to copy share of symbols gross present in the second annotation that are also present in the first"""
        pp2 = self.basic_measures.pp_[2]
        self.performance_measures.set_value('pp2', pp2)
    def _calc_pa(self):
        """Method to copy share of symbols present exclusively in the first annotation"""
        pa = self.basic_measures.pa
        self.performance_measures.set_value('pa', pa)
    def _calc_ap(self):
        """Method to copy share of symbols present exclusively in the second annotation"""
        ap = self.basic_measures.ap
        self.performance_measures.set_value('ap', ap)
    def _calc_aa(self):
        """Method to copy share of symbols absent in both annotation"""
        aa = self.basic_measures.aa
        self.performance_measures.set_value('aa', aa)
    def _calc_rc2(self):
        """Method to calculate symbol-wise recall for the second annotation"""
        denominator = self.basic_measures.pp_[1] + self.basic_measures.pa
        rc2 = self.basic_measures.pp_[1] / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('rc2', rc2)
    def _calc_pr2(self):
        """Method to calculate symbol-wise precision for the second annotation"""
        denominator = self.basic_measures.pp_[2] + self.basic_measures.ap
        pr2 = self.basic_measures.pp_[2] / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('pr2', pr2)
    def _calc_sp2(self):
        """Method to calculate symbol-wise specificity for the second annotation"""
        denominator = self.basic_measures.aa + self.basic_measures.ap
        sp2 = self.basic_measures.aa / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('sp2', sp2)
    def _calc_npv2(self):
        """Method to calculate symbol-wise negative predictive value for the second annotation"""
        denominator = self.basic_measures.aa + self.basic_measures.pa
        npv2 = self.basic_measures.aa / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('npv2', npv2)
    def _calc_in2(self):
        """Method to calculate symbol-wise informedness for the second annotation"""
        in2 = self.performance_measures.get_value('rc2') + self.performance_measures.get_value('sp2') - 1
        self.performance_measures.set_value('in2', in2)
    def _calc_mk2(self):
        """Method to calculate symbol-wise markedness for the second annotation"""
        mk2 = self.performance_measures.get_value('pr2') + self.performance_measures.get_value('npv2') - 1
        self.performance_measures.set_value('mk2', mk2)
    def _calc_pc(self):
        """Method to calculate symbol-wise performance coefficient"""
        denominator = self.basic_measures.pp_[2] + self.basic_measures.ap + self.basic_measures.pa
        pc = self.basic_measures.pp_[2] / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('pc', pc)
    def _calc_acc(self):
        """Method to calculate symbol-wise accuracy ACC"""
        acc = self.basic_measures.pp + self.basic_measures.aa
        self.performance_measures.set_value('acc', acc)
    def _calc_mcc(self):
        """Method to calculate symbol-wise Matthews correlation coefficient"""
        numerator = self.basic_measures.pp * self.basic_measures.aa + self.basic_measures.ap * self.basic_measures.pa
        temp = (self.basic_measures.pp + self.basic_measures.pa) * (self.basic_measures.pp + self.basic_measures.ap) * (self.basic_measures.aa + self.basic_measures.ap) * (self.basic_measures.aa + self.basic_measures.pa)
        mcc = numerator / math.sqrt(temp) if temp > 0.0 else float('nan')
        self.performance_measures.set_value('mcc', mcc)
    def _calc_f1(self):
        """Method to calculate symbol-wise F1 score"""
        denominator = 2 * self.basic_measures.pp_[1] * self.basic_measures.pp_[2] + self.basic_measures.pp_[2] * self.basic_measures.pa + self.basic_measures.pp_[1] * self.basic_measures.ap
        f1 = 2 * self.basic_measures.pp_[1] * self.basic_measures.pp_[2] / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('f1', f1)
    def _calc_site_n1(self):
        """Method to calculate number of sites in the first annotation"""
        site_n1 = self.basic_measures.site_m[1] + self.basic_measures.site_nm[1]
        self.performance_measures.set_value('site_n1', site_n1)
    def _calc_site_n2(self):
        """Method to calculate number of sites in the second annotation"""
        site_n2 = self.basic_measures.site_m[2] + self.basic_measures.site_nm[2]
        self.performance_measures.set_value('site_n2', site_n2)
    def _calc_site_len1(self):
        """Method to copy total length of sites in the first annotation"""
        site_len1 = self.basic_measures.site_len[1]
        self.performance_measures.set_value('site_len1', site_len1)
    def _calc_site_len2(self):
        """Method to copy total length of sites in the second annotation"""
        site_len2 = self.basic_measures.site_len[2]
        self.performance_measures.set_value('site_len2', site_len2)
    def _calc_site_rc2(self):
        """Method to calculate site-wise recall for the second annotation"""
        denominator = self.basic_measures.site_m[1] + self.basic_measures.site_nm[1]
        site_rc2 = self.basic_measures.site_m[1] / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('site_rc2', site_rc2)
    def _calc_site_pr2(self):
        """Method to calculate site-wise recall for the second annotation"""
        denominator = self.basic_measures.site_m[2] + self.basic_measures.site_nm[2]
        site_pr2 = self.basic_measures.site_m[2] / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('site_pr2', site_pr2)
    def _calc_site_pc2(self):
        """Method to calculate site-wise performance coefficient for the second annotation"""
        denominator = self.basic_measures.site_m[2] + self.basic_measures.site_nm[2] + self.basic_measures.site_nm[1]
        site_pc2 = self.basic_measures.site_m[2] / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('site_pc2', site_pc2)
    def _calc_site_f1(self):
        """Method to calculate site-wise F1 score"""
        temp = 2 * self.basic_measures.site_m[1] * self.basic_measures.site_m[2]
        denominator = temp + self.basic_measures.site_nm[1] * self.basic_measures.site_m[2] + self.basic_measures.site_nm[2] * self.basic_measures.site_m[1]
        site_f1 = temp / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('site_f1', site_f1)
    def _calc_site_pcv(self):
        """Method to calculate site-wise positive correlation value"""
        temp = self.basic_measures.site_m[1] + self.basic_measures.site_m[2]
        denominator = temp + self.basic_measures.site_nm[1] + self.basic_measures.site_nm[2]
        site_pcv = temp / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('site_pcv', site_pcv)
    def _calc_e_p1(self):
        """Method to copy share of symbols enriched in the first annotation"""
        e_p1 = self.basic_measures.e[1]
        self.performance_measures.set_value('e_p1', e_p1)
    def _calc_e_p2(self):
        """Method to copy share of symbols enriched in the second annotation"""
        e_p2 = self.basic_measures.e[2]
        self.performance_measures.set_value('e_p2', e_p2)
    def _calc_e_pp(self):
        """Method to copy share of symbols enriched in both annotations"""
        e_pp = self.basic_measures.ee
        self.performance_measures.set_value('e_pp', e_pp)
    def _calc_e_pa(self):
        """Method to calculate share of symbols enriched exclusively in the first annotation"""
        e_pa = self.basic_measures.e[1] - self.basic_measures.ee
        self.performance_measures.set_value('e_pa', e_pa)
    def _calc_e_ap(self):
        """Method to calculate share of symbols enriched exclusively in the second annotation"""
        e_ap = self.basic_measures.e[2] - self.basic_measures.ee
        self.performance_measures.set_value('e_ap', e_ap)
    def _calc_e_aa(self):
        """Method to copy share of symbols enriched in neither annotation"""
        e_aa = self.basic_measures.ne
        self.performance_measures.set_value('e_aa', e_aa)
    def _calc_e_rc2(self):
        """Method to calculate symbol-wise enrichment recall for the second annotation"""
        e_rc2 = self.basic_measures.ee / self.basic_measures.e[1] if self.basic_measures.e[1] > 0.0 else float('nan')
        self.performance_measures.set_value('e_rc2', e_rc2)
    def _calc_e_pr2(self):
        """Method to calculate symbol-wise enrichment precision for the second annotation"""
        e_pr2 = self.basic_measures.ee / self.basic_measures.e[2] if self.basic_measures.e[2] > 0.0 else float('nan')
        self.performance_measures.set_value('e_pr2', e_pr2)
    def _calc_e_sp2(self):
        """Method to calculate symbol-wise enrichment specificity for the second annotation"""
        denominator = 1 - self.basic_measures.e[1]
        e_sp2 = self.basic_measures.ne / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('e_sp2', e_sp2)
    def _calc_e_npv2(self):
        """Method to calculate symbol-wise enrichment negative predictive value for the second annotation"""
        denominator = 1 - self.basic_measures.e[2]
        e_npv2 = self.basic_measures.ne / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('e_npv2', e_npv2)
    def _calc_e_in2(self):
        """Method to calculate symbol-wise enrichment informedness for the second annotation"""
        e_in2 = self.performance_measures.get_value('e_rc2') + self.performance_measures.get_value('e_sp2') - 1
        self.performance_measures.set_value('e_in2', e_in2)
    def _calc_e_mk2(self):
        """Method to calculate symbol-wise enrichment markedness for the second annotation"""
        e_mk2 = self.performance_measures.get_value('e_pr2') + self.performance_measures.get_value('e_npv2') - 1
        self.performance_measures.set_value('e_mk2', e_mk2)
    def _calc_e_pc(self):
        """Method to calculate symbol-wise enrichment performance coefficient"""
        denominator = 1 - self.basic_measures.ne
        e_pc = self.basic_measures.ee / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('e_pc', e_pc)
    def _calc_e_acc(self):
        """Method to calculate symbol-wise enrichment accuracy ACC"""
        e_acc = self.basic_measures.ee + self.basic_measures.ne
        self.performance_measures.set_value('e_acc', e_acc)
    def _calc_e_mcc(self):
        """Method to calculate symbol-wise enrichment Matthews correlation coefficient"""
        only_in_1 = self.basic_measures.e[1] - self.basic_measures.ee
        only_in_2 = self.basic_measures.e[2] - self.basic_measures.ee
        numerator = self.basic_measures.ee * self.basic_measures.ne + only_in_1 * only_in_2
        denominator = math.sqrt((self.basic_measures.ee + only_in_1) * (self.basic_measures.ee + only_in_2) * (self.basic_measures.ne + only_in_1) * (self.basic_measures.ne + only_in_2))
        e_mcc = numerator / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('e_mcc', e_mcc)
    def _calc_e_f1(self):
        """Method to calculate symbol-wise enrichment F1 score"""
        denominator = self.basic_measures.e[1] + self.basic_measures.e[2]
        e_f1 = 2 * self.basic_measures.ee / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('e_f1', e_f1)
    def _calc_e_eac(self):
        """Method to calculate enrichment asymmetry coefficient"""
        denominator = self.basic_measures.e[1] + self.basic_measures.e[2] - self.basic_measures.ee
        e_eac = (self.basic_measures.re[1] + self.basic_measures.re[2]) / denominator if denominator > 0.0 else float('nan')
        self.performance_measures.set_value('e_eac', e_eac)
    def _calc_seq_n(self):
        """Method to copy the number of sequences in the group"""
        seq_n = self.basic_measures.seq_n
        self.performance_measures.set_value('seq_n', seq_n)
    def process_group(self, GID):
        """Method to calculate all relevant count performance measures for a giben sequence group"""
        basic_calculator = BasicCalculator(self.global_state, self.opt, self.input_data, self.file_handlers)
        self.basic_measures = basic_calculator.process_group(GID)
        self.performance_measures = PerformanceMeasures(self.opt.enrichment_count, self.opt.benchmark, self.opt.gross)
        for measure in self.performance_measures.name_map:
            getattr(self, '_calc_' + measure.var_name)()
        return self.performance_measures

class DataProcessor:
    """Class to calculate and save into corresponding files performance measures as well as output annotations for each group and the whole database"""
    def __init__(self, opt, global_state, input_data):
        self.opt = opt
        self.input_data = input_data
        self.file_handlers = FileHandlers()
        self.global_state = global_state
        self.performance_calculator = PerformanceCalculator(global_state, opt, input_data, self.file_handlers)
        self.database_results = PerformanceMeasures(self.opt.enrichment_count, self.opt.benchmark, self.opt.gross)
    def _float_to_fixed_width_str(value, width):
        """Method to make the best attempt to represent a float as fixed-width string"""
        for i in range(width - 2, -1, -1):
            str0 = '{:.{}f}'.format(value, i)
            if len(str0) <= width:
                break
        return str0
    def _open_output_files(self):
        """Method to open required output annotation files"""
        for type_ in FileHandlers.output_file_types:
            filepath = getattr(self.opt, 'output_file_' + type_)
            if not filepath:
                continue
            file_handler = open(filepath, 'w')
            if type_ == 'detailed':
                pass
            elif type_ == 'site':
                header = ('GID\t' if self.opt.group_map else '') + 'SID\tAnnotation\tSite begin\tSite end\t'
                if self.opt.site_names:
                    header += 'Site name\t'
                if self.opt.overlap_apply == 'patched':
                    header += 'Matched symbols\tMatched perc.\n'
                else:
                    header += 'Overlapped symbols\tOverlapped perc.\tPartner overlapped perc.\tPartner begin\tPartner end'
                if self.opt.site_names:
                    header += '\tPartner name'
                file_handler.write(header + os.linesep)
            else:
                header = ('GID\t' if self.opt.group_map else '') + 'SID\tbegin\tend\n'
                file_handler.write(header)
            setattr(self.file_handlers, type_, file_handler)
    def _close_output_files(self):
        """Method to close ouptput annotation files"""
        for type_ in FileHandlers.output_file_types:
            handler = getattr(self.file_handlers, type_)
            if handler is None:
                continue
            handler.close()
            filepath = getattr(self.opt, 'output_file_' + type_)
            description = type_
            description.replace('complement', 'complement of')
            description = re.sub('$re', 'relative enrichment for', description)
            description.replace('1', ' the first')
            description.replace('1', ' the second')
            if type_ == 'detailed':
                output_type = 'output'
            elif type_ == 'site':
                output_type = 'statistics'
            else:
                output_type = 'annotatiion'
            description += ' ' + output_type
            print("The {} file '{}' has been written".format(description, filepath))
    def _generate_header(self, grouped):
        """Method to form the header with basic launch information as well as relevant column names"""
        header = ''
        if not self.opt.clean:
            header += "# This file was generated at {} with THE METHOD".format(str(datetime.datetime.now())[: -7]) + os.linesep
            header += '# Command line options (unquoted and unescaped): ' + ' '.join(sys.argv[1: ]) + os.linesep
            header += '# The following statistics have been calculated:' + os.linesep
        column_names = 'GID\t' if grouped else ''
        for measure in self.database_results.name_map:
            if not self.opt.clean:
                header += '#    {}: {}'.format(measure.displayed_name, measure.description) + os.linesep
            column_names += measure.displayed_name + '\t'
        header += column_names + os.linesep
        return header
    def _produce_final_string(self, results, attr_names, na_zeros, groups_n):
        """Method to calculate database-wide averages of relevance performance measures and save them to the string"""
        final_string = 'Average\t' if groups_n else ''
        for attr_name in attr_names:
            value = results.get_value(attr_name)
            if not na_zeros:
                if not math.isnan(value):
                    value = value / results.get_count(attr_name) if groups_n else value
            else:
                if math.isnan(value):
                    value = 0.0
                else:
                    value = value / groups_n if groups_n else value
            final_string += (str(value) if type(value)==int else DataProcessor._float_to_fixed_width_str(value, 6)) + '\t'
        return final_string[: -1] 
    def process(self):
        """Method to coordinate the input data processing and outputting"""
        self._open_output_files()
        with open(self.opt.output_file, 'w') as ofile:
            header = self._generate_header(self.opt.group_map)
            ofile.write(header)
            attr_names = [x.var_name for x in self.database_results.name_map]
            if self.opt.group_map:
                for GID in self.input_data.group_map.keys():
                    group_results = self.performance_calculator.process_group(GID)
                    row = GID
                    for attr_name in attr_names:
                        value = group_results.get_value(attr_name)
                        value = '{:.4f}'.format(value) if type(value) != int else str(value)
                        row += '\t' + value
                    ofile.write(row + os.linesep)
                    self.database_results += group_results
                if not self.opt.clean:
                    ofile.write('-' * (8 * (len(attr_names) + 1)) + os.linesep)
                groups_n = len(self.input_data.group_map)
            else:
                self.database_results = self.performance_calculator.process_group('')
                groups_n = 0
            if (not self.opt.clean) or (groups_n == 0):
                ofile.write(self._produce_final_string(self.database_results, attr_names, self.opt.na_zeros, groups_n))
        print("The output file '{}' with performance measures has been written".format(self.opt.output_file))
        self._close_output_files()
            
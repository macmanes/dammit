#!/usr/bin/env python
from __future__ import print_function

from doit.action import CmdAction
from doit.tools import title_with_actions, LongRunning
from doit.task import clean_targets
import os
import pandas as pd

from .parallel import parallel_fasta, multinode_parallel_fasta
from .parallel import get_filesize_task
from . import parsers
from .utils import doit_task, which


@doit_task
def get_hmmscan_task(input_filename, output_filename, db_filename,
                     cutoff=0.00001, n_threads=1, n_nodes=None, 
                     params=None):

    name = 'hmmscan:' + os.path.basename(input_filename) + '.x.' + \
                    os.path.basename(db_filename)
    stat = output_filename + '.hmmscan.out'
    def hmmscan_cmd(file_size):

        hmmscan_exc = which('hmmscan')
        
        if n_nodes is None:
            parallel_cmd = parallel_fasta(input_filename, n_threads, file_size)
        else:
            parallel_cmd = multinode_parallel_fasta(input_filename, n_threads,
                                                    n_nodes, file_size)

        cmd = [parallel_cmd, hmmscan_exc]
        if params is not None:
            cmd.extend([str(p) for p in params])
        cmd.extend(['--cpu', '1', '--domtblout', '/dev/stdout', 
                    '-E', str(cutoff), '-o', stat, db_filename, '/dev/stdin',
                    '>', output_filename])

        return ' '.join(cmd)
        
    return {'name': name,
            'title': title_with_actions,
            'actions': [LongRunning(hmmscan_cmd)],
            'file_dep': [input_filename, db_filename, db_filename+'.h3p'],
            'targets': [output_filename, stat],
            'getargs': {'file_size': ('get_filesize:{0}'.format(input_filename),
                                      'size')},
            'clean': [clean_targets]}


@doit_task
def get_hmmpress_task(db_filename, params=None, task_dep=None):

    name = 'hmmpress:' + os.path.basename(db_filename)
    exc = which('hmmpress')

    cmd = [exc]
    if params is not None:
        cmd.extend([str(p) for p in params])
    cmd.append(db_filename)

    cmd = ' '.join(cmd)

    task_d =  {'name': name,
              'title': title_with_actions,
              'actions': [cmd],
              'targets': [db_filename + ext for ext in ['.h3f', '.h3i', '.h3m', '.h3p']],
              'uptodate': [True],
              'clean': [clean_targets]}
    if task_dep is not None:
        task_d['task_dep'] = task_dep

    return task_d


@doit_task
def get_remap_hmmer_task(hmmer_filename, remap_gff_filename, output_filename):

    name = 'remap_hmmer:{0}'.format(os.path.basename(hmmer_filename))

    def cmd():
        gff_df = pd.concat(parsers.parse_gff3(remap_gff_filename))
        hmmer_df = pd.concat(parsers.hmmscan_to_df_iter(hmmer_filename))

        merged_df = pd.merge(hmmer_df, gff_df, left_on='full_query_name', right_on='ID')

        hmmer_df['env_coord_from'] = (merged_df.start + \
                                      (3 * merged_df.env_coord_from)).astype(int)
        hmmer_df['env_coord_to'] = (merged_df.start + \
                                    (3 * merged_df.env_coord_to)).astype(int)
        hmmer_df['ali_coord_from'] = (merged_df.start + \
                                      (3 * merged_df.ali_coord_from)).astype(int)
        hmmer_df['ali_coord_to'] = (merged_df.start + \
                                    (3 * merged_df.ali_coord_to)).astype(int)

        hmmer_df.to_csv(output_filename, header=True, index=False)

    return {'name': name,
            'title': title_with_actions,
            'actions': [cmd],
            'file_dep': [hmmer_filename, remap_gff_filename],
            'targets': [output_filename],
            'clean': [clean_targets]}


def hmmscan(input_filename, output_filename, db_filename, **hmmscan_kwds):
    '''Wrapper for `get_hmmscan_task`. Yields a filesize_task
    and an hmmscan_task.'''



    yield get_filesize_task(input_filename)
    yield get_hmmscan_task(input_filename, output_filename, db_filename,
                           **hmmscan_kwds)
"""Author presentation-only records for native UMG recycled list entries."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from ui_authoring import *

bp = unreal.load_asset(ROOT + '/BP_UIListItem') or BP.create(ROOT, 'BP_UIListItem', unreal.Object.static_class())
graphs = declare(bp, {'name':'Kind Key Status', 'string':'RunId', 'int':'Revision Index Count', 'bool':'Known', 'text':'Title Subtitle Detail'},
                 {'ResetItem':([], [('Result','bool')])}, {'Owner':unreal.Object.static_class()})
object_array_variable(bp, 'Children', unreal.Object.static_class())
graphs = declare(bp, {}, {'ResetItem':([], [('Result','bool')])})
emit(bp, graphs, {'ResetItem': f'''(fn ResetItem ()
    {put('Kind','"None"')} {put('Key','"None"')} {put('Status','"None"')} {put('RunId','""')}
    {put('Revision','-1')} {put('Index','-1')} {put('Count','0')} {put('Known','false')}
    {put('Title',text('""'))} {put('Subtitle',text('""'))} {put('Detail',text('""'))}
    (Utilities|Array|Clear {g('Children')}) (return true))'''})
unreal.log('WO_UI_LIST_ITEM_GENERATED')

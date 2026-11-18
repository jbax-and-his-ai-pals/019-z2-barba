-- Carock's own bolts hit harder than Attack 7 breath when returned with Reflect.
dofile(TEST_DIR..'/boss_fight.lua')
runBossFight{name='carock_reflect',world=4,region=1,number=4,room=0x1C,page=0,kind=4,
    bosses={[0x22]=true},final=0x22,attack=7,reflect=true,frames=6000,exitPage=3,
    checks=function(check,fight)
        check(fight.reflectHits==2,'Carock takes exactly two reflected bolts')
    end}

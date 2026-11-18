-- Palace 4 Carock takes three fireballs at Attack 7 (CarockHit, bank 4 $A7D0): fireball-only
-- kill with no thrust techniques, native boss death (no sprite-0 NMI hang), key drop,
-- scroll unlock and exit through the locked door.
dofile(TEST_DIR..'/boss_fight.lua')
runBossFight{name='carock',world=4,region=1,number=4,room=0x1C,page=0,kind=4,
    bosses={[0x22]=true},final=0x22,attack=7,frames=6000,exitPage=3,
    checks=function(check,fight)
        check(fight.seen[0x22],'Carock ($22) spawned in room $1C')
        check(fight.fireHits==3,'Carock takes exactly three Attack 7 fireballs')
    end}

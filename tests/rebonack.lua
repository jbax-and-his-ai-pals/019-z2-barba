-- Palace 3 Rebonack without Downward Thrust: fireballs unhorse him ($20, HP < $24)
-- and beat the dismounted knight ($0A), then the key unlocks the room. Guards against a
-- softlock for players who skip Downward Thrust (and the old stomp kill that dropped no key).
dofile(TEST_DIR..'/boss_fight.lua')
runBossFight{name='rebonack',world=4,region=0,number=3,room=0x0E,page=0,kind=4,
    bosses={[0x20]=true,[0x0A]=true},final=0x0A,attack=5,frames=12000,exitPage=2,
    checks=function(check,fight)
        check(fight.seen[0x20],'mounted Rebonack ($20) spawned in room $0E')
        check((fight.damage[0x20] or 0)>=36,'fireballs took mounted Rebonack below the dismount threshold')
        check(fight.seen[0x0A],'Rebonack dismounted ($0A knight)')
        check((fight.damage[0x0A] or 0)>0,'fireballs damaged the dismounted knight')
    end}

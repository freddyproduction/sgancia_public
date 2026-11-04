import {describe,it,expect} from 'vitest'
import {readInvitation} from './inviteLink'
const token='example-invitation-token-12345'
describe('invitation link routing',()=>{
 it('prefills account registration only for the explicit new-account link',()=>{
  expect(readInvitation(`http://localhost:8088/invite?register=1#${token}`)).toEqual({token,register:true})
  expect(readInvitation(`http://localhost:8088/invite#${token}`)).toEqual({token,register:false})
 })
 it('does not accept a token from query strings, guest links or malformed fragments',()=>{
  expect(readInvitation(`http://localhost:8088/invite?token=${token}`)).toBeNull()
  expect(readInvitation(`http://localhost:8088/guest#${token}`)).toBeNull()
  expect(readInvitation('http://localhost:8088/invite#not valid')).toBeNull()
 })
})

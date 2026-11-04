import {describe,it,expect,vi,afterEach} from 'vitest'
import {parseGroupCode} from './JoinGroup'
afterEach(()=>vi.unstubAllGlobals())
describe('group access links and codes',()=>{
 it('separates guest viewing from member and association codes',()=>{
  vi.stubGlobal('location',{origin:'http://localhost:8088'})
  const token='synthetic_group_code_123456789'
  expect(parseGroupCode(' '+token+' ').token).toBe(token)
  expect(parseGroupCode('http://localhost:8088/invite#'+token).token).toBe(token)
  expect(parseGroupCode('http://localhost:8088/guest#'+token)).toEqual({guest:'http://localhost:8088/guest#'+token,token:''})
 })
 it('rejects another installation, unexpected routes and credential-bearing URLs',()=>{
  vi.stubGlobal('location',{origin:'http://localhost:8088'})
  for(const value of ['https://evil.test/invite#synthetic_group_code','http://localhost:8088/admin#synthetic_group_code','http://user:password@localhost:8088/guest#synthetic_group_code','short'])expect(()=>parseGroupCode(value)).toThrow()
 })
})

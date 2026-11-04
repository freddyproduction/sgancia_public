import type {Group} from './api'
export function GroupAvatar({group,className='group-avatar'}:{group:Group;className?:string}){return <span className={className}>{group.image_url?<img src={group.image_url} alt=""/>:<span>{group.icon||'✳'}</span>}</span>}

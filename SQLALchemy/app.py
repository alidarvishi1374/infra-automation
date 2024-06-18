# SQLAlchemy

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.expression import and_



# database = library://username:pass@db_address:port/db_name
engine = create_engine('sqlite:///:database.db')
session = sessionmaker(bind=engine)()


base = declarative_base()

class Student(base):
    __tablename__ = 'student'
    _id = Column('id', Integer, unique=True, primary_key=True)
    name = Column('name', String(50))


base.metadata.create_all(engine)


# SELECT
# students = session.query(Student).filter(and_(Student._id=="1",Student.name=="ali")).order_by(Student._id).all()


# for student in students:
#     print(student._id, student.name)

# INSERT
# student_1 = Student(name="Reza")
# student_2 = Student(name="Alireza")
# student_3 = Student(name="Gholi")
# student_4 = Student(name="Taghi")

# session.add_all([student_1,student_2, student_3, student_4])

# session.commit()

# DELETE

students = session.query(Student).filter(Student.name=="Gholi").delete()
session.commit()

# for _student in students:
#     session.delete(_student)
#     session.commit()


# UPDATE

session.query(Student).filter(Student.name=="Taghi").update({'name':'taghiiii'})
session.commit()








